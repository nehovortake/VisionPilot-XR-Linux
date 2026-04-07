import argparse
from pathlib import Path
import cv2
import numpy as np

SPEED_CLASSES = {"10","20","30","40","50","60","70","80","90","100","110","130"}

# Default params (existing CLI args still work as defaults)
DEFAULT_INNER_SCALE = 0.75
DEFAULT_FOCUS_SCALE = 0.90

CLASS_OVERRIDES = {
    "100": {"inner_scale": 0.95, "focus_scale": 1.00, "crop_mode": "crop"},
    "110": {"inner_scale": 1.00, "focus_scale": 1.00, "crop_mode": "crop"},
    "130": {"inner_scale": 0.95, "focus_scale": 1.00, "crop_mode": "crop"},
}

def preprocess_inner_mask(img_bgr, out_size=64, inner_scale=0.75, focus_scale=0.90, crop_mode="crop"):
    """
    inner_scale: how much of the inner disk we keep (ring suppression)
    focus_scale: center crop scale to "zoom digits"
        1.00 = no zoom
        0.90 = mild zoom
        0.85 = stronger zoom
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
        # Pad to square (no cutting of 3-digit signs)
        h2, w2 = inner.shape
        s0 = max(h2, w2)
        canvas = np.zeros((s0, s0), dtype=inner.dtype)

        y_off = (s0 - h2) // 2
        x_off = (s0 - w2) // 2
        canvas[y_off:y_off + h2, x_off:x_off + w2] = inner

        # optional zoom AFTER padding (usually keep 1.00 for 110/130)
        s = int(s0 * focus_scale)
        s = max(8, min(s, s0))

        cx2, cy2 = s0 // 2, s0 // 2
        x0 = max(0, cx2 - s // 2)
        y0 = max(0, cy2 - s // 2)
        x0 = min(x0, s0 - s)
        y0 = min(y0, s0 - s)

        inner = canvas[y0:y0 + s, x0:x0 + s]

    else:
        # Original behavior: center square crop by min(h,w)
        s0 = min(h, w)
        s = int(s0 * focus_scale)
        s = max(8, min(s, s0))

        x0 = max(0, cx - s // 2)
        y0 = max(0, cy - s // 2)
        x0 = min(x0, w - s)
        y0 = min(y0, h - s)

        inner = inner[y0:y0 + s, x0:x0 + s]


    # 3) resize
    inner = cv2.resize(inner, (out_size, out_size), interpolation=cv2.INTER_AREA)
    return inner


def main():
    ap = argparse.ArgumentParser()

    # ✅ Default added so you can run without arguments
    ap.add_argument(
        "--dataset_root",
        default=r"C:\Users\Minko\Desktop\DP\VisionPilot-XR Win\dataset",
        help="Root folder containing class subfolders 10, 20, 30..."
    )

    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--inner_scale", type=float, default=0.75)
    ap.add_argument("--focus_scale", type=float, default=0.90)
    ap.add_argument("--exts", nargs="+", default=[".png", ".jpg", ".jpeg", ".bmp"])
    args = ap.parse_args()

    root = Path(args.dataset_root)

    if not root.exists():
        print(f"Dataset root not found: {root}")
        return

    class_dirs = [d for d in root.iterdir() if d.is_dir() and d.name in SPEED_CLASSES]
    if not class_dirs:
        print("No class folders found (10,20,30...).")
        return

    for d in sorted(class_dirs, key=lambda x: int(x.name)):

        # Pick params for this class (override for 110/130)
        override = CLASS_OVERRIDES.get(d.name, {})
        inner_scale = float(override.get("inner_scale", args.inner_scale))
        focus_scale = float(override.get("focus_scale", args.focus_scale))
        crop_mode = override.get("crop_mode", "crop")

        # DEBUG PRINT (dočasne)
        print(f"[CLASS {d.name}] focus_scale={focus_scale} crop_mode={crop_mode}")

        # Create suffix per class (so folder reflects real params)
        suffix = f"resize_{args.size}_fs{focus_scale}_is{inner_scale}"
        out_dir = root / f"{d.name} {suffix}"
        out_dir.mkdir(parents=True, exist_ok=True)

        files = []
        for ext in args.exts:
            files.extend(d.rglob(f"*{ext}"))

        if not files:
            print(f"[{d.name}] no images found.")
            continue

        saved = 0
        skipped = 0

        for p in sorted(files):
            img = cv2.imread(str(p))
            if img is None:
                skipped += 1
                continue

            patch = preprocess_inner_mask(
                img,
                out_size=args.size,
                inner_scale=inner_scale,
                focus_scale=focus_scale,
                crop_mode=crop_mode
            )

            if patch is None:
                skipped += 1
                continue

            out_path = out_dir / p.name
            if cv2.imwrite(str(out_path), patch):
                saved += 1
            else:
                skipped += 1

        print(f"[{d.name}] -> {out_dir.name}: saved={saved}, skipped={skipped}")

    print("All done.")


if __name__ == "__main__":
    main()