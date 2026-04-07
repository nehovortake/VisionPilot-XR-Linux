import argparse
from pathlib import Path
import random
import csv
import os
import sys
import subprocess

import cv2
import numpy as np
import matplotlib.pyplot as plt


SPEED_CLASSES = ["10", "20", "30", "40", "50", "60", "70", "80", "90", "100", "110", "130"]
IMG_EXTS = [".png", ".jpg", ".jpeg", ".bmp"]

# rovnaké defaulty ako v process_all_classes.py
DEFAULT_INNER_SCALE = 0.75
DEFAULT_FOCUS_SCALE = 0.90

CLASS_OVERRIDES = {
    "100": {"inner_scale": 0.95, "focus_scale": 1.00, "crop_mode": "crop"},
    "110": {"inner_scale": 1.00, "focus_scale": 1.00, "crop_mode": "pad"},
    "130": {"inner_scale": 0.95, "focus_scale": 1.00, "crop_mode": "pad"},
}


def preprocess_inner_mask(img_bgr, out_size=64, inner_scale=0.75, focus_scale=0.90, crop_mode="crop"):
    """
    - potlačí okraj kruhu (inner_scale)
    - urobí crop alebo pad (crop_mode)
    - následne resize na out_size
    Výstup: grayscale uint8 (64x64)
    """
    if img_bgr is None or img_bgr.size == 0:
        return None

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    h, w = gray.shape
    cx, cy = w // 2, h // 2

    # 1) inner circular mask
    r = int(inner_scale * 0.5 * min(w, h))
    mask = np.zeros_like(gray, np.uint8)
    cv2.circle(mask, (cx, cy), r, 255, -1)
    inner = cv2.bitwise_and(gray, gray, mask=mask)

    # 2) crop / pad strategy
    if crop_mode == "pad":
        # pad do štvorca (aby sa 3-ciferné neodrezali)
        h2, w2 = inner.shape
        s0 = max(h2, w2)
        canvas = np.zeros((s0, s0), dtype=inner.dtype)

        y_off = (s0 - h2) // 2
        x_off = (s0 - w2) // 2
        canvas[y_off:y_off + h2, x_off:x_off + w2] = inner

        # optional zoom po pade
        s = int(s0 * focus_scale)
        s = max(8, min(s, s0))

        cx2, cy2 = s0 // 2, s0 // 2
        x0 = max(0, cx2 - s // 2)
        y0 = max(0, cy2 - s // 2)
        x0 = min(x0, s0 - s)
        y0 = min(y0, s0 - s)

        inner = canvas[y0:y0 + s, x0:x0 + s]
    else:
        # center crop
        s0 = min(h, w)
        s = int(s0 * focus_scale)
        s = max(8, min(s, s0))

        x0 = max(0, cx - s // 2)
        y0 = max(0, cy - s // 2)
        x0 = min(x0, w - s)
        y0 = min(y0, h - s)

        inner = inner[y0:y0 + s, x0:x0 + s]

    inner = cv2.resize(inner, (out_size, out_size), interpolation=cv2.INTER_AREA)
    return inner


def list_images(class_dir: Path):
    files = []
    for ext in IMG_EXTS:
        files.extend(class_dir.rglob(f"*{ext}"))
    return sorted(files)


def save_counts(out_dir: Path, counts: dict):
    # CSV
    csv_path = out_dir / "class_counts.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["class", "count"])
        for c in SPEED_CLASSES:
            w.writerow([c, counts.get(c, 0)])

    # TXT summary
    txt_path = out_dir / "class_counts.txt"
    total = sum(counts.values())
    lines = [f"TOTAL: {total}\n"]
    for c in SPEED_CLASSES:
        lines.append(f"{c}: {counts.get(c, 0)}\n")
    txt_path.write_text("".join(lines), encoding="utf-8")


def plot_histogram(out_dir: Path, counts: dict):
    classes = SPEED_CLASSES
    values = [counts.get(c, 0) for c in classes]

    plt.figure()
    plt.bar(classes, values)
    plt.title("Dataset class distribution")
    plt.xlabel("Class")
    plt.ylabel("Image count")
    plt.tight_layout()

    out_path = out_dir / "class_distribution.png"
    plt.savefig(out_path, dpi=200)
    plt.close()


def make_grid(images_gray: list, rows: int, cols: int, cell_size: int = 64, pad: int = 2):
    """
    images_gray: list of 2D uint8 images (64x64)
    returns: uint8 grid image
    """
    H = rows * cell_size + (rows + 1) * pad
    W = cols * cell_size + (cols + 1) * pad
    grid = np.full((H, W), 255, dtype=np.uint8)  # biele pozadie

    k = 0
    for r in range(rows):
        for c in range(cols):
            y = pad + r * (cell_size + pad)
            x = pad + c * (cell_size + pad)
            if k < len(images_gray) and images_gray[k] is not None:
                im = images_gray[k]
                if im.shape != (cell_size, cell_size):
                    im = cv2.resize(im, (cell_size, cell_size), interpolation=cv2.INTER_AREA)
                grid[y:y + cell_size, x:x + cell_size] = im
            k += 1
    return grid


def save_grid_png(out_path: Path, grid_gray: np.ndarray):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), grid_gray)


def build_preprocessed_samples(files: list, out_size: int, inner_scale: float, focus_scale: float, crop_mode: str, max_samples: int):
    samples = []
    for p in files[:max_samples]:
        img = cv2.imread(str(p))
        if img is None:
            continue
        patch = preprocess_inner_mask(
            img,
            out_size=out_size,
            inner_scale=inner_scale,
            focus_scale=focus_scale,
            crop_mode=crop_mode
        )
        if patch is not None:
            samples.append(patch)
    return samples


# ======================================================
# DOPLNENÉ: BEFORE (farebný) + BEFORE/AFTER GRID (farebný výstup)
# ======================================================

def to_preview_bgr(img_bgr, out_size=64):
    """
    "Pred" náhľad: farebný BGR + center square crop, resize na out_size.
    """
    if img_bgr is None or img_bgr.size == 0:
        return None
    h, w = img_bgr.shape[:2]
    s = min(h, w)
    x0 = (w - s) // 2
    y0 = (h - s) // 2
    crop = img_bgr[y0:y0 + s, x0:x0 + s]
    crop = cv2.resize(crop, (out_size, out_size), interpolation=cv2.INTER_AREA)
    return crop


def make_before_after_grid_color_before(before_bgr_list, after_gray_list, rows, cols, cell_size=64, pad=2, gap=6):
    """
    Grid kde každý tile je dvojica:
    BEFORE (farebné BGR) | AFTER (grayscale -> prevedené do BGR)
    Výstup je BGR image (H,W,3), aby sa dala uložiť farebne.
    """
    assert len(before_bgr_list) == len(after_gray_list)
    pair_w = 2 * cell_size + gap
    H = rows * cell_size + (rows + 1) * pad
    W = cols * pair_w + (cols + 1) * pad
    grid = np.full((H, W, 3), 255, dtype=np.uint8)  # biely BGR

    k = 0
    for r in range(rows):
        for c in range(cols):
            y = pad + r * (cell_size + pad)
            x = pad + c * (pair_w + pad)

            if k < len(before_bgr_list):
                b = before_bgr_list[k]
                a = after_gray_list[k]

                if b is not None:
                    if b.shape[:2] != (cell_size, cell_size):
                        b = cv2.resize(b, (cell_size, cell_size), interpolation=cv2.INTER_AREA)
                    grid[y:y + cell_size, x:x + cell_size] = b

                if a is not None:
                    if a.shape != (cell_size, cell_size):
                        a = cv2.resize(a, (cell_size, cell_size), interpolation=cv2.INTER_AREA)
                    a_bgr = cv2.cvtColor(a, cv2.COLOR_GRAY2BGR)
                    x2 = x + cell_size + gap
                    grid[y:y + cell_size, x2:x2 + cell_size] = a_bgr

            k += 1

    return grid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project_root", default=".", help="Root of VisionPilot-XR (default: current folder)")
    ap.add_argument("--dataset_root", default="dataset", help="Dataset folder (relative to project_root or absolute)")
    ap.add_argument("--out_size", type=int, default=64)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--per_class_grid", type=int, default=25, help="How many samples per class into grid (e.g. 25 = 5x5)")
    ap.add_argument("--mix_grid", type=int, default=64, help="How many mixed samples into one grid (e.g. 64 = 8x8)")
    ap.add_argument("--before_after_pairs", type=int, default=36, help="How many BEFORE/AFTER pairs (square: 36=6x6, 49=7x7, 64=8x8)")
    args = ap.parse_args()

    random.seed(args.seed)

    project_root = Path(args.project_root).resolve()
    dataset_root = Path(args.dataset_root)
    if not dataset_root.is_absolute():
        dataset_root = (project_root / dataset_root).resolve()

    out_dir = project_root / "MLP_report" / "01_dataset_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not dataset_root.exists():
        print(f"[ERROR] Dataset root not found: {dataset_root}")
        return

    # 1) COUNTS
    counts = {}
    class_files_map = {}

    for c in SPEED_CLASSES:
        d = dataset_root / c
        if not d.exists():
            counts[c] = 0
            class_files_map[c] = []
            continue
        files = list_images(d)
        counts[c] = len(files)
        class_files_map[c] = files

    save_counts(out_dir, counts)
    plot_histogram(out_dir, counts)

    # 2) PER-CLASS PREPROCESS GRID (64x64)
    per_class_dir = out_dir / "preprocessed_grids_per_class"
    per_class_dir.mkdir(parents=True, exist_ok=True)

    grid_n = args.per_class_grid
    grid_side = int(np.sqrt(grid_n))
    if grid_side * grid_side != grid_n:
        grid_side = int(np.floor(np.sqrt(grid_n)))
        grid_n = grid_side * grid_side

    for c in SPEED_CLASSES:
        files = class_files_map.get(c, [])
        if len(files) == 0:
            continue

        override = CLASS_OVERRIDES.get(c, {})
        inner_scale = float(override.get("inner_scale", DEFAULT_INNER_SCALE))
        focus_scale = float(override.get("focus_scale", DEFAULT_FOCUS_SCALE))
        crop_mode = override.get("crop_mode", "crop")

        chosen = files.copy()
        random.shuffle(chosen)
        chosen = chosen[:grid_n]

        patches = build_preprocessed_samples(
            chosen,
            out_size=args.out_size,
            inner_scale=inner_scale,
            focus_scale=focus_scale,
            crop_mode=crop_mode,
            max_samples=grid_n
        )

        grid = make_grid(patches, rows=grid_side, cols=grid_side, cell_size=args.out_size, pad=2)
        save_grid_png(per_class_dir / f"class_{c}_grid_{grid_side}x{grid_side}.png", grid)

    # 3) MIXED GRID (naprieč triedami)
    mixed_dir = out_dir / "preprocessed_grids_mixed"
    mixed_dir.mkdir(parents=True, exist_ok=True)

    mix_n = args.mix_grid
    mix_side = int(np.sqrt(mix_n))
    if mix_side * mix_side != mix_n:
        mix_side = int(np.floor(np.sqrt(mix_n)))
        mix_n = mix_side * mix_side

    all_candidates = []
    for c in SPEED_CLASSES:
        files = class_files_map.get(c, [])
        if not files:
            continue
        tmp = files.copy()
        random.shuffle(tmp)
        take = max(1, mix_n // len(SPEED_CLASSES))
        all_candidates.extend([(c, p) for p in tmp[:take]])

    random.shuffle(all_candidates)
    all_candidates = all_candidates[:mix_n]

    mixed_patches = []
    for (c, p) in all_candidates:
        img = cv2.imread(str(p))
        if img is None:
            continue
        override = CLASS_OVERRIDES.get(c, {})
        inner_scale = float(override.get("inner_scale", DEFAULT_INNER_SCALE))
        focus_scale = float(override.get("focus_scale", DEFAULT_FOCUS_SCALE))
        crop_mode = override.get("crop_mode", "crop")

        patch = preprocess_inner_mask(img, out_size=args.out_size, inner_scale=inner_scale, focus_scale=focus_scale, crop_mode=crop_mode)
        if patch is not None:
            mixed_patches.append(patch)

    mixed_grid = make_grid(mixed_patches, rows=mix_side, cols=mix_side, cell_size=args.out_size, pad=2)
    save_grid_png(mixed_dir / f"mixed_grid_{mix_side}x{mix_side}.png", mixed_grid)

    # 4) EXTRA: ukážka rozdielu crop vs pad (2-digit vs 3-digit)
    compare_dir = out_dir / "compare_2digit_vs_3digit"
    compare_dir.mkdir(parents=True, exist_ok=True)

    left_class = "90"
    right_class = "110"
    left_files = class_files_map.get(left_class, [])
    right_files = class_files_map.get(right_class, [])

    if left_files and right_files:
        random.shuffle(left_files)
        random.shuffle(right_files)

        left_patches = build_preprocessed_samples(
            left_files[:12],
            out_size=args.out_size,
            inner_scale=DEFAULT_INNER_SCALE,
            focus_scale=DEFAULT_FOCUS_SCALE,
            crop_mode="crop",
            max_samples=12
        )

        right_patches = build_preprocessed_samples(
            right_files[:12],
            out_size=args.out_size,
            inner_scale=float(CLASS_OVERRIDES.get("110", {}).get("inner_scale", 1.0)),
            focus_scale=float(CLASS_OVERRIDES.get("110", {}).get("focus_scale", 1.0)),
            crop_mode="pad",
            max_samples=12
        )

        grid_top = make_grid(left_patches, rows=3, cols=4, cell_size=args.out_size, pad=2)
        grid_bot = make_grid(right_patches, rows=3, cols=4, cell_size=args.out_size, pad=2)

        spacer = np.full((10, grid_top.shape[1]), 255, dtype=np.uint8)
        combined = np.vstack([grid_top, spacer, grid_bot])

        save_grid_png(compare_dir / "compare_90_crop_vs_110_pad.png", combined)

    # ======================================================
    # 5) DOPLNENÉ: BEFORE (farebné) / AFTER (gray) GRID
    # ======================================================
    before_after_dir = out_dir / "before_after_grids"
    before_after_dir.mkdir(parents=True, exist_ok=True)

    ba_n = args.before_after_pairs
    ba_side = int(np.sqrt(ba_n))
    if ba_side * ba_side != ba_n:
        ba_side = int(np.floor(np.sqrt(ba_n)))
        ba_n = ba_side * ba_side

    pairs = []
    per_class_take = max(1, ba_n // len(SPEED_CLASSES))
    for c in SPEED_CLASSES:
        files = class_files_map.get(c, [])
        if not files:
            continue
        tmp = files.copy()
        random.shuffle(tmp)
        pairs.extend([(c, p) for p in tmp[:per_class_take]])

    random.shuffle(pairs)
    pairs = pairs[:ba_n]

    before_bgr_list = []
    after_gray_list = []

    for (c, p) in pairs:
        img = cv2.imread(str(p))
        if img is None:
            continue

        before_bgr = to_preview_bgr(img, out_size=args.out_size)

        override = CLASS_OVERRIDES.get(c, {})
        inner_scale = float(override.get("inner_scale", DEFAULT_INNER_SCALE))
        focus_scale = float(override.get("focus_scale", DEFAULT_FOCUS_SCALE))
        crop_mode = override.get("crop_mode", "crop")

        after_gray = preprocess_inner_mask(
            img,
            out_size=args.out_size,
            inner_scale=inner_scale,
            focus_scale=focus_scale,
            crop_mode=crop_mode
        )

        if before_bgr is not None and after_gray is not None:
            before_bgr_list.append(before_bgr)
            after_gray_list.append(after_gray)

    m = min(len(before_bgr_list), len(after_gray_list))
    m_side = int(np.floor(np.sqrt(m)))
    m = m_side * m_side
    before_bgr_list = before_bgr_list[:m]
    after_gray_list = after_gray_list[:m]

    if m > 0:
        grid_ba = make_before_after_grid_color_before(
            before_bgr_list,
            after_gray_list,
            rows=m_side,
            cols=m_side,
            cell_size=args.out_size,
            pad=2,
            gap=6
        )
        cv2.imwrite(str(before_after_dir / f"before_after_mixed_colorBefore_{m_side}x{m_side}.png"), grid_ba)

    # finálny info súbor
    (out_dir / "README.txt").write_text(
        "Generated:\n"
        "- class_counts.csv / class_counts.txt\n"
        "- class_distribution.png\n"
        "- preprocessed_grids_per_class/*.png\n"
        "- preprocessed_grids_mixed/*.png\n"
        "- compare_2digit_vs_3digit/compare_90_crop_vs_110_pad.png (if data exists)\n"
        "- before_after_grids/before_after_mixed_colorBefore_*.png (BEFORE=BGR preview | AFTER=preprocess gray)\n",
        encoding="utf-8"
    )

    print(f"[OK] Dataset analysis report saved to: {out_dir}")

    # ======================================================
    # 6) DOPLNENÉ: AUTOMATICKÉ OTVORENIE FOLDERA
    # ======================================================
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(out_dir))
        elif sys.platform.startswith("darwin"):
            subprocess.Popen(["open", str(out_dir)])
        else:
            subprocess.Popen(["xdg-open", str(out_dir)])
    except Exception as e:
        print(f"[WARN] Could not auto-open folder: {e}")


if __name__ == "__main__":
    main()
