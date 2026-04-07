# error_analysis_report.py
from __future__ import annotations

import argparse
import csv
import os
import sys
import platform
import subprocess
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

import numpy as np
import cv2
import torch
import matplotlib.pyplot as plt

from mlp_explain_utils import (
    load_mlp_checkpoint,
    predict_with_auto_preprocess,
    IMG_SIZE_DEFAULT,
)

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


# ======================================================
# Helpers: OS open folder
# ======================================================
def open_folder(path: Path):
    try:
        if platform.system() == "Windows":
            os.startfile(str(path))
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


# ======================================================
# GT parsing: dataset/<class>/image.png
# ======================================================
def try_get_gt_from_parent(img_path: Path) -> int | None:
    try:
        name = img_path.parent.name.strip()
        if name.isdigit():
            return int(name)
    except Exception:
        pass
    return None


def iter_images(folder: Path):
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS:
            yield p


# ======================================================
# Explainability: SmoothGrad (lightweight)
# ======================================================
def smoothgrad_saliency(model, x, class_idx: int, n_samples=20, noise_std=0.08):
    """
    SmoothGrad: average |grad| over noisy inputs.
    x: (1,4096) float in [0,1]
    return: (4096,) float
    """
    base = x.detach()
    grads = []

    for _ in range(n_samples):
        noise = torch.randn_like(base) * noise_std
        xn = (base + noise).clamp(0, 1).requires_grad_(True)

        model.zero_grad(set_to_none=True)
        logits = model(xn)
        logits[0, class_idx].backward()

        g = xn.grad.detach().abs()
        grads.append(g)

    gmean = torch.stack(grads, dim=0).mean(dim=0)
    return gmean.squeeze(0).detach().cpu().numpy()


def heat_overlay_on_gray(patch_gray: np.ndarray, heat01: np.ndarray) -> np.ndarray:
    """
    patch_gray: uint8 (64,64)
    heat01: float32 (64,64) in [0,1]
    return overlay RGB uint8
    """
    base = patch_gray.astype(np.float32) / 255.0
    heat = cv2.applyColorMap((heat01 * 255).astype(np.uint8), cv2.COLORMAP_JET)
    heat = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    overlay = np.clip(0.65 * np.dstack([base, base, base]) + 0.55 * heat, 0, 1)
    return (overlay * 255).astype(np.uint8)


# ======================================================
# Error heuristics: blur / small / cropped
# ======================================================
def blur_score_variance_of_laplacian(img_gray: np.ndarray) -> float:
    # nízke hodnoty = rozmazané
    return float(cv2.Laplacian(img_gray, cv2.CV_64F).var())


def estimate_crop_risk(patch_gray: np.ndarray) -> float:
    """
    Jednoduchý indikátor, či číslica "naráža" na okraj patchu.
    Ak je veľa tmavých pixelov pri okrajoch -> crop risk.
    """
    g = patch_gray
    # binarizácia pre odhad obsahu
    _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # číslica je typicky tmavá -> invert pre "ink"
    ink = (255 - bw)  # 0..255
    ink01 = (ink > 0).astype(np.uint8)

    h, w = ink01.shape
    m = max(2, int(0.08 * min(h, w)))  # 8% okraj

    border = np.zeros_like(ink01)
    border[:m, :] = 1
    border[-m:, :] = 1
    border[:, :m] = 1
    border[:, -m:] = 1

    ink_border = int((ink01 * border).sum())
    ink_total = int(ink01.sum())
    if ink_total == 0:
        return 0.0
    return float(ink_border / ink_total)  # 0..1 (vyššie = horšie)


def estimate_small_digit(patch_gray: np.ndarray) -> float:
    """
    Odhad veľkosti číslice v patchi: pomer 'ink' plochy.
    Ak je príliš malé -> malý ink ratio.
    """
    g = patch_gray
    _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ink = (255 - bw)
    ink01 = (ink > 0).astype(np.uint8)
    ratio = float(ink01.mean())  # 0..1
    return ratio


@dataclass
class ErrorCase:
    path: Path
    gt: int
    pred: int
    top1: int
    top1_pct: float
    top2: int
    top2_pct: float
    margin: float
    blur_var: float
    crop_risk: float
    ink_ratio: float


# ======================================================
# Main
# ======================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_root", type=str, default=r"C:\Users\Minko\Desktop\DP\VisionPilot-XR Win\dataset",
                    help="dataset folder with class subfolders (10/20/.../130)")
    ap.add_argument("--model", type=str, default=None,
                    help="Path to mlp_speed_model.pt (default: dataset_root/mlp_speed_model.pt)")
    ap.add_argument("--in_dir", type=str, default=None,
                    help="Folder to scan (default: dataset_root)")
    ap.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda"])
    ap.add_argument("--limit_scan", type=int, default=0, help="0 = scan all images")
    ap.add_argument("--top_errors", type=int, default=40, help="How many wrong images to export")
    ap.add_argument("--sort_by", type=str, default="lowest_margin",
                    choices=["lowest_margin", "highest_confidence_wrong"],
                    help="How to rank error cases")
    ap.add_argument("--smooth_n", type=int, default=20)
    ap.add_argument("--smooth_std", type=float, default=0.08)
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root)
    model_path = Path(args.model) if args.model else (dataset_root / "mlp_speed_model.pt")
    in_dir = Path(args.in_dir) if args.in_dir else dataset_root

    # output
    project_root = dataset_root.parent  # VisionPilot-XR
    base_out = project_root / "MLP_report" / "05_error_analysis"
    base_out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = base_out / f"error_analysis__{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_images = out_dir / "cases"
    out_images.mkdir(parents=True, exist_ok=True)

    # device
    device = args.device if (args.device == "cpu" or torch.cuda.is_available()) else "cpu"

    loaded = load_mlp_checkpoint(model_path, device=device)
    model, labels = loaded.model, loaded.labels
    labels_int = [int(x) for x in labels]

    # --------------------------------------------------
    # Scan images and collect wrong predictions
    # --------------------------------------------------
    errors: list[ErrorCase] = []

    n = 0
    for p in iter_images(in_dir):
        img = cv2.imread(str(p))
        if img is None:
            continue

        gt = try_get_gt_from_parent(p)
        if gt is None:
            # bez GT nevieš označiť "wrong", preskočíme
            continue

        patch, x, logits, pred_idx, pred_label = predict_with_auto_preprocess(
            model=model,
            labels=labels_int,
            img_bgr=img,
            img_size=IMG_SIZE_DEFAULT,
            device=device,
        )

        probs = torch.softmax(logits, dim=1).detach().cpu().numpy().squeeze(0)
        top2 = np.argsort(-probs)[:2]
        t1, t2 = int(top2[0]), int(top2[1])

        top1_label = int(labels_int[t1])
        top2_label = int(labels_int[t2])

        top1_pct = float(probs[t1] * 100.0)
        top2_pct = float(probs[t2] * 100.0)
        margin = top1_pct - top2_pct

        pred = int(pred_label)

        if pred != int(gt):
            # heuristics
            gray_full = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blur_var = blur_score_variance_of_laplacian(gray_full)
            crop_risk = estimate_crop_risk(patch)
            ink_ratio = estimate_small_digit(patch)

            errors.append(ErrorCase(
                path=p,
                gt=int(gt),
                pred=pred,
                top1=top1_label,
                top1_pct=top1_pct,
                top2=top2_label,
                top2_pct=top2_pct,
                margin=margin,
                blur_var=blur_var,
                crop_risk=crop_risk,
                ink_ratio=ink_ratio,
            ))

        n += 1
        if args.limit_scan > 0 and n >= args.limit_scan:
            break

    if not errors:
        (out_dir / "README.txt").write_text(
            "No error cases found.\n"
            "- Ensure you run on dataset folder structure dataset/<class>/image.png\n"
            "- Or ensure GT can be inferred from parent folder name.\n",
            encoding="utf-8"
        )
        print("[ERROR_ANALYSIS] No error cases found. Output:", out_dir)
        open_folder(out_dir)
        return

    # --------------------------------------------------
    # Rank errors
    # --------------------------------------------------
    if args.sort_by == "lowest_margin":
        errors.sort(key=lambda e: e.margin)  # najneistejšie chyby
    else:
        errors.sort(key=lambda e: -e.top1_pct)  # najsebavedomejšie chyby

    selected = errors[: max(1, args.top_errors)]

    # --------------------------------------------------
    # Export CSV summary
    # --------------------------------------------------
    summary_csv = out_dir / "errors_summary.csv"
    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "file", "gt", "pred",
            "top1", "top1_pct", "top2", "top2_pct", "margin_pct",
            "blur_var_laplacian", "crop_risk", "ink_ratio",
            "notes"
        ])
        for e in selected:
            notes = []
            # blur threshold (heuristic): < ~80 often blurry on typical sign crops
            if e.blur_var < 80.0:
                notes.append("BLUR")
            # small digit ratio threshold
            if e.ink_ratio < 0.06:
                notes.append("SMALL_DIGIT")
            # crop risk threshold
            if e.crop_risk > 0.25:
                notes.append("CROPPED_EDGE")

            w.writerow([
                str(e.path),
                e.gt, e.pred,
                e.top1, f"{e.top1_pct:.2f}",
                e.top2, f"{e.top2_pct:.2f}",
                f"{e.margin:.2f}",
                f"{e.blur_var:.2f}",
                f"{e.crop_risk:.3f}",
                f"{e.ink_ratio:.3f}",
                "|".join(notes)
            ])

    # --------------------------------------------------
    # For each error: save a single "case sheet" PNG
    # --------------------------------------------------
    for idx, e in enumerate(selected, start=1):
        img_bgr = cv2.imread(str(e.path))
        if img_bgr is None:
            continue

        patch, x, logits, pred_idx, pred_label = predict_with_auto_preprocess(
            model=model,
            labels=labels_int,
            img_bgr=img_bgr,
            img_size=IMG_SIZE_DEFAULT,
            device=device,
        )

        # SmoothGrad on predicted class index
        # pred_idx is index in labels list, which matches logits dim
        sal_vec = smoothgrad_saliency(
            model=model,
            x=x,
            class_idx=int(pred_idx),
            n_samples=args.smooth_n,
            noise_std=args.smooth_std
        )
        sal = sal_vec.reshape(IMG_SIZE_DEFAULT, IMG_SIZE_DEFAULT).astype(np.float32)
        sal = (sal - sal.min()) / (sal.max() - sal.min() + 1e-6)
        overlay = heat_overlay_on_gray(patch, sal)

        # prepare nice figure
        rgb_full = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        rgb_patch = cv2.cvtColor(patch, cv2.COLOR_GRAY2RGB)
        rgb_patch = cv2.resize(rgb_patch, (256, 256), interpolation=cv2.INTER_NEAREST)
        rgb_overlay = cv2.resize(overlay, (256, 256), interpolation=cv2.INTER_NEAREST)

        # notes
        notes = []
        if e.blur_var < 80.0:
            notes.append("BLUR")
        if e.ink_ratio < 0.06:
            notes.append("SMALL_DIGIT")
        if e.crop_risk > 0.25:
            notes.append("CROPPED_EDGE")
        notes_txt = " | ".join(notes) if notes else "OK (heuristics)"

        title = (
            f"ERROR #{idx:02d} | GT={e.gt}  PRED={e.pred} | "
            f"Top1={e.top1} ({e.top1_pct:.1f}%)  Top2={e.top2} ({e.top2_pct:.1f}%) | "
            f"Margin={e.margin:.2f}%\n"
            f"BlurVar={e.blur_var:.1f}  InkRatio={e.ink_ratio:.3f}  CropRisk={e.crop_risk:.3f} | {notes_txt}\n"
            f"{e.path.parent.name}/{e.path.name}"
        )

        fig = plt.figure(figsize=(14, 6))
        gs = fig.add_gridspec(2, 3, height_ratios=[1, 1])

        ax0 = fig.add_subplot(gs[:, 0])
        ax0.imshow(rgb_full)
        ax0.set_title("Originál (farebný vstup)")
        ax0.axis("off")

        ax1 = fig.add_subplot(gs[0, 1])
        ax1.imshow(rgb_patch)
        ax1.set_title("Patch 64×64 (čo vidí MLP)")
        ax1.axis("off")

        ax2 = fig.add_subplot(gs[0, 2])
        ax2.imshow(rgb_overlay)
        ax2.set_title("SmoothGrad overlay (citlivé pixely)")
        ax2.axis("off")

        ax3 = fig.add_subplot(gs[1, 1])
        ax3.imshow(sal, cmap="hot")
        ax3.set_title("SmoothGrad heatmap")
        ax3.axis("off")

        # info panel
        ax4 = fig.add_subplot(gs[1, 2])
        ax4.axis("off")
        txt = (
            f"GT: {e.gt}\n"
            f"PRED: {e.pred}\n\n"
            f"Top1: {e.top1}  {e.top1_pct:.2f}%\n"
            f"Top2: {e.top2}  {e.top2_pct:.2f}%\n"
            f"Margin: {e.margin:.2f}%\n\n"
            f"BlurVar (Laplacian): {e.blur_var:.2f}\n"
            f"InkRatio: {e.ink_ratio:.3f}\n"
            f"CropRisk: {e.crop_risk:.3f}\n\n"
            f"Heuristics: {notes_txt}\n"
        )
        ax4.text(0.0, 1.0, txt, va="top", fontsize=12)

        fig.suptitle(title, fontsize=12)
        fig.tight_layout()

        out_png = out_images / f"error_{idx:02d}__gt{e.gt}__pred{e.pred}__margin{e.margin:.1f}.png"
        plt.savefig(str(out_png), dpi=170)
        plt.close(fig)

    # --------------------------------------------------
    # README for obhajoba
    # --------------------------------------------------
    readme = out_dir / "README.txt"
    readme.write_text(
        "05_error_analysis report generated.\n\n"
        "Files:\n"
        "- errors_summary.csv: tabuľka chybných prípadov + margin + heuristiky\n"
        "- cases/*.png: každý prípad má originál (farebný), patch 64×64, SmoothGrad, a metriky\n\n"
        "Heuristics:\n"
        "- BLUR: Laplacian variance < ~80 (indikácia rozmazania)\n"
        "- SMALL_DIGIT: ink_ratio < ~0.06 (číslica málo pixelov v patchi)\n"
        "- CROPPED_EDGE: crop_risk > ~0.25 (číslica zasahuje do okraja patchu)\n\n"
        "Interpretácia:\n"
        "- Margin (Top1%-Top2%) hovorí stabilitu rozhodnutia.\n"
        "- SmoothGrad ukazuje, či sa model pozerá na tvar číslic, alebo na okraj/šum.\n",
        encoding="utf-8"
    )

    print("[ERROR_ANALYSIS] Saved to:", out_dir)
    print("[ERROR_ANALYSIS] Summary CSV:", summary_csv)
    print("[ERROR_ANALYSIS] Cases PNG:", out_images)
    open_folder(out_dir)


if __name__ == "__main__":
    main()
