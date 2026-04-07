# mlp_explain_report.py
from __future__ import annotations

from pathlib import Path
import argparse
from datetime import datetime
import sys
import os
import platform
import subprocess
import csv
from collections import defaultdict

import numpy as np
import cv2
import torch
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QApplication, QFileDialog

from mlp_explain_utils import load_mlp_checkpoint, predict_with_auto_preprocess, IMG_SIZE_DEFAULT

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


# -------------------------------------------------
# Folder picker – začne presne v dataset priečinku
# -------------------------------------------------
def pick_folder(start_dir: str) -> str | None:
    app = QApplication.instance()
    created = False
    if app is None:
        app = QApplication(sys.argv)
        created = True

    folder = QFileDialog.getExistingDirectory(
        None,
        "Vyber priečinok (napr. dataset\\110 alebo celý dataset)",
        start_dir
    )

    if created:
        app.quit()

    return folder if folder else None


def open_folder(path: Path):
    try:
        if platform.system() == "Windows":
            os.startfile(str(path))
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        print("[REPORT][WARN] Could not open folder:", e)


def try_get_gt_from_parent(img_path: Path) -> int | None:
    """
    Ground-truth (GT) berieme z názvu nadradeného priečinka:
      ...\\dataset\\110\\image.png  -> GT=110
    """
    try:
        name = img_path.parent.name.strip()
        if name.isdigit():
            return int(name)
    except Exception:
        pass
    return None


def infer_sign_prefix_from_selected_folder(in_dir: Path, dataset_root: Path) -> str:
    """
    Prefix do názvu výstupného priečinka.
    - Ak je in_dir priamo dataset\\110 -> prefix '110'
    - Inak -> 'mixed'
    """
    try:
        if in_dir.is_dir() and in_dir.name.isdigit() and in_dir.parent.resolve() == dataset_root.resolve():
            return in_dir.name
        if in_dir.name.isdigit():
            return in_dir.name
    except Exception:
        pass
    return "mixed"


def iter_images(folder: Path):
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS:
            yield p


# ----------------------------
# Plot helpers
# ----------------------------
def plot_margin_hist(margins: list[float], out_path: Path):
    if not margins:
        return
    plt.figure()
    plt.hist(margins, bins=30)
    plt.title("Top-1 Margin Distribution (Top1% - Top2%)")
    plt.xlabel("Margin (%)")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(str(out_path), dpi=200)
    plt.close()


def plot_per_class_accuracy(per_gt_total: dict[int, int], per_gt_correct: dict[int, int], out_path: Path):
    if not per_gt_total:
        return
    classes = sorted(per_gt_total.keys())
    accs = []
    for c in classes:
        tot = per_gt_total.get(c, 0)
        cor = per_gt_correct.get(c, 0)
        acc = (cor / tot * 100.0) if tot > 0 else 0.0
        accs.append(acc)

    plt.figure(figsize=(10, 4))
    plt.bar([str(c) for c in classes], accs)
    plt.title("Per-class Accuracy (GT from folder name)")
    plt.xlabel("Class")
    plt.ylabel("Accuracy (%)")
    plt.tight_layout()
    plt.savefig(str(out_path), dpi=200)
    plt.close()


def safe_rel_name(img_path: Path, in_dir: Path) -> str:
    try:
        rel = str(img_path.relative_to(in_dir))
    except Exception:
        rel = img_path.name
    return rel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_root", type=str, default=r"C:\Users\Minko\Desktop\DP\VisionPilot-XR Win\dataset")
    ap.add_argument("--model", type=str, default=None)
    ap.add_argument("--in_dir", type=str, default=None)  # ak None -> folder dialog
    ap.add_argument("--img_size", type=int, default=IMG_SIZE_DEFAULT)
    ap.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda"])
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root)
    model_path = Path(args.model) if args.model else (dataset_root / "mlp_speed_model.pt")

    # ------------------------------
    # Výber vstupného foldra
    # ------------------------------
    if args.in_dir is None:
        picked = pick_folder(str(dataset_root))
        if not picked:
            print("[REPORT] No folder selected. Exiting.")
            return
        in_dir = Path(picked)
    else:
        in_dir = Path(args.in_dir)

    # -------------------------------------------------
    # OUTPUT: 03_runtime_validation
    # -------------------------------------------------
    project_root = dataset_root.parent  # ...\VisionPilot-XR
    base_out = project_root / "MLP_report" / "03_runtime_validation"
    base_out.mkdir(parents=True, exist_ok=True)

    sign_prefix = infer_sign_prefix_from_selected_folder(in_dir, dataset_root)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = base_out / f"{sign_prefix}__runtime_validation__{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # files
    per_image_csv = out_dir / "runtime_summary.csv"
    aggregate_txt = out_dir / "aggregate_report.txt"
    hardest_csv = out_dir / "hardest_classes.csv"

    # ------------------------------
    # Load model
    # ------------------------------
    device = args.device if (args.device == "cpu" or torch.cuda.is_available()) else "cpu"
    loaded = load_mlp_checkpoint(model_path, device=device)
    model, labels = loaded.model, loaded.labels

    # ------------------------------
    # Aggregácia
    # ------------------------------
    total = 0
    total_with_gt = 0
    correct = 0

    margins_all: list[float] = []
    margins_gt: list[float] = []

    per_gt_total = defaultdict(int)
    per_gt_correct = defaultdict(int)
    per_gt_margin_sum = defaultdict(float)

    # ------------------------------
    # CSV per-image (to čo chceš na obhajobu)
    # ------------------------------
    with open(per_image_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "filename",
            "gt",
            "pred",
            "top1",
            "top1_pct",
            "top2",
            "top2_pct",
            "margin_pct",
            "is_correct"
        ])

        n = 0
        for img_path in iter_images(in_dir):
            img = cv2.imread(str(img_path))
            if img is None:
                continue

            patch, x, logits, pred_idx, pred_label = predict_with_auto_preprocess(
                model=model,
                labels=labels,
                img_bgr=img,
                img_size=args.img_size,
                device=device,
            )

            probs = torch.softmax(logits, dim=1).detach().cpu().numpy().squeeze(0)
            top2 = np.argsort(-probs)[:2]
            t1, t2 = int(top2[0]), int(top2[1])

            t1p = float(probs[t1] * 100.0)
            t2p = float(probs[t2] * 100.0)

            margin = t1p - t2p  # Top-1 margin = Top-2 difference
            margins_all.append(margin)

            rel_name = safe_rel_name(img_path, in_dir)

            gt = try_get_gt_from_parent(img_path)
            is_correct = ""
            if gt is not None:
                total_with_gt += 1
                per_gt_total[gt] += 1
                per_gt_margin_sum[gt] += margin
                margins_gt.append(margin)

                if int(pred_label) == int(gt):
                    correct += 1
                    per_gt_correct[gt] += 1
                    is_correct = "1"
                else:
                    is_correct = "0"

            writer.writerow([
                rel_name,
                "" if gt is None else int(gt),
                int(pred_label),
                int(labels[t1]),
                f"{t1p:.2f}",
                int(labels[t2]),
                f"{t2p:.2f}",
                f"{margin:.2f}",
                is_correct
            ])

            total += 1
            n += 1
            if args.limit > 0 and n >= args.limit:
                break

    # ------------------------------
    # Aggregate metrics
    # ------------------------------
    avg_margin_all = float(np.mean(margins_all)) if margins_all else 0.0
    med_margin_all = float(np.median(margins_all)) if margins_all else 0.0

    avg_margin_gt = float(np.mean(margins_gt)) if margins_gt else 0.0
    med_margin_gt = float(np.median(margins_gt)) if margins_gt else 0.0

    acc = (correct / total_with_gt * 100.0) if total_with_gt > 0 else None

    # Hardest classes: zoradiť podľa acc asc, potom avg margin asc
    hardest = []
    for gt, cnt in per_gt_total.items():
        c = per_gt_correct.get(gt, 0)
        a = (c / cnt * 100.0) if cnt > 0 else 0.0
        m = (per_gt_margin_sum[gt] / cnt) if cnt > 0 else 0.0
        hardest.append((a, m, gt, cnt, c))
    hardest.sort(key=lambda x: (x[0], x[1]))

    # uložiť hardest CSV
    if hardest:
        with open(hardest_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["gt", "acc_pct", "avg_margin_pct", "count", "correct"])
            for (a, m, gt, cnt, c) in hardest[:20]:
                w.writerow([gt, f"{a:.2f}", f"{m:.2f}", cnt, c])

    # grafy
    plot_margin_hist(margins_all, out_dir / "margin_hist.png")
    plot_per_class_accuracy(per_gt_total, per_gt_correct, out_dir / "per_class_accuracy.png")

    # ------------------------------
    # Text report (obhajoba-ready)
    # ------------------------------
    with open(aggregate_txt, "w", encoding="utf-8") as f:
        f.write("MLP Runtime Validation Report\n")
        f.write("====================================\n\n")
        f.write(f"Input folder (in_dir): {in_dir}\n")
        f.write(f"Model: {model_path}\n")
        f.write(f"Device: {device}\n")
        f.write(f"Output folder: {out_dir}\n\n")

        f.write(f"Total processed images: {total}\n")
        f.write(f"Average Top-1 margin (all): {avg_margin_all:.2f}%\n")
        f.write(f"Median  Top-1 margin (all): {med_margin_all:.2f}%\n\n")

        if acc is None:
            f.write("GT could NOT be determined from parent folder names.\n")
            f.write("Tip: použij štruktúru dataset\\110\\image.png aby sa rátala accuracy per class.\n")
        else:
            f.write(f"Images with GT detected: {total_with_gt}\n")
            f.write(f"Accuracy (GT only): {correct} / {total_with_gt}  = {acc:.2f}%\n")
            f.write(f"Average Top-1 margin (GT only): {avg_margin_gt:.2f}%\n")
            f.write(f"Median  Top-1 margin (GT only): {med_margin_gt:.2f}%\n\n")

            f.write("Hardest classes (lowest accuracy, then lowest avg margin):\n")
            f.write("  GT | Acc% | AvgMargin% | Count | Correct\n")
            for (a, m, gt, cnt, c) in hardest[:10]:
                f.write(f"  {gt:>3} | {a:>6.2f} | {m:>9.2f} | {cnt:>5} | {c:>7}\n")

        f.write("\nFiles generated:\n")
        f.write("- runtime_summary.csv (per-image top1/top2/margin + GT)\n")
        f.write("- aggregate_report.txt\n")
        f.write("- hardest_classes.csv\n")
        f.write("- margin_hist.png\n")
        f.write("- per_class_accuracy.png\n")

    print("[REPORT] Done.")
    print("[REPORT] Saved outputs into:", out_dir)
    print("[REPORT] runtime_summary.csv:", per_image_csv)
    print("[REPORT] aggregate_report.txt:", aggregate_txt)
    print("[REPORT] hardest_classes.csv:", hardest_csv)

    open_folder(out_dir)


if __name__ == "__main__":
    main()
