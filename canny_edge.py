"""Canny edge detection utilities aligned with image_processing.apply_canny.

- canny_edges: uses image_processing.apply_canny under the hood (manual thresholds).
- overlay_edges: unchanged helper for visualization.
"""
from __future__ import annotations

import argparse
from typing import Tuple
import cv2
import numpy as np
import os, sys

# Ensure local project root is first on sys.path so imports prefer local modules
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

try:
    # Prefer a real 'image_processing' module if it exists and provides apply_canny
    import image_processing as _ip
    if hasattr(_ip, 'apply_canny'):
        _apply_canny = _ip.apply_canny
    else:
        raise ImportError("installed 'image_processing' does not expose apply_canny")
except Exception:
    # Provide a local implementation compatible with expected behavior
    def _apply_canny(image, t1, t2, sigma):
        """Local fallback for apply_canny: grayscale -> GaussianBlur -> cv2.Canny

        Parameters mirror the original: t1, t2 thresholds and sigma for blur.
        """
        try:
            if image is None:
                return image
            # Ensure single-channel input
            if len(image.shape) == 3:
                img_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                img_gray = image

            # Compute odd kernel size from sigma (keep reasonable bounds)
            k = max(1, int(round(sigma)))
            ksize = 2 * k + 1
            h, w = img_gray.shape[:2]
            # ensure ksize is odd and <= min(h,w)
            ksize = max(3, min(ksize, min(h | 1, w | 1)))

            blurred = cv2.GaussianBlur(img_gray, (ksize, ksize), sigma)
            t1_i, t2_i = sorted((int(t1), int(t2)))
            return cv2.Canny(blurred, t1_i, t2_i)
        except Exception:
            # As ultimate fallback, use a small fixed blur
            try:
                if len(image.shape) == 3:
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                else:
                    gray = image
                blurred = cv2.GaussianBlur(gray, (5, 5), 1.0)
                return cv2.Canny(blurred, int(t1), int(t2))
            except Exception:
                return image

# import preprocessing helpers
from red_nuling_preprocessing import keep_only_red

# Default manual Canny parameters
DEFAULT_T1 = 80
DEFAULT_T2 = 150
DEFAULT_SIGMA = 3.0


def _to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def canny_edges(img: np.ndarray, t1: float = 80.0, t2: float = 150.0, sigma: float = 1.0) -> np.ndarray:
    """Compute Canny edges using the same behavior as image_processing.apply_canny."""
    return _apply_canny(img, int(t1), int(t2), float(sigma))


def manual_canny_edges(img: np.ndarray) -> np.ndarray:
    """Manual Canny using module defaults (DEFAULT_T1/T2/SIGMA)."""
    return _apply_canny(img, int(DEFAULT_T1), int(DEFAULT_T2), float(DEFAULT_SIGMA))


def overlay_edges(
    img: np.ndarray,
    edges: np.ndarray,
    color: Tuple[int, int, int] = (255, 255, 255),
    alpha: float = 1.0,
) -> np.ndarray:
    """Fast edge overlay - just convert edges to BGR (white on black)."""
    # Fast path: if alpha is 1.0, just show edges as white on black
    if alpha >= 0.99:
        # Convert grayscale edges to BGR
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

    # Slow path: blend edges with original (rarely used)
    if img.ndim == 2:
        base = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    else:
        base = img.copy()

    # Create edge overlay more efficiently
    edge_mask = edges > 0
    base[edge_mask] = color
    return base


def _cli():
    p = argparse.ArgumentParser(description="Run Canny edge detection on an image")
    p.add_argument("--in", dest="in_path", required=True, help="Input image path")
    p.add_argument("--out", dest="out_path", default=None, help="Optional output path for edges or overlay")
    p.add_argument("--sigma", type=float, default=1.0, help="Gaussian blur sigma before Canny (manual mode)")
    p.add_argument("--t1", type=float, default=80.0, help="Manual Canny threshold1")
    p.add_argument("--t2", type=float, default=150.0, help="Manual Canny threshold2")
    p.add_argument("--overlay", action="store_true", help="Save/show overlay instead of raw edges")
    p.add_argument("--mix", action="store_true", help="Use LAB+CLAHE + red-null mix as Canny input (for red signs)")
    args = p.parse_args()

    img = cv2.imread(args.in_path, cv2.IMREAD_COLOR)
    if img is None:
        print(f"Failed to load {args.in_path}")
        return

    # optional preprocessing - simplified: use red-nulling mix directly (no LAB+CLAHE)
    if args.mix:
        print("🔧 Using red-null mix preprocessing before Canny (no LAB/CLAHE)...")
        try:
            red_only, mix = keep_only_red(img, return_mix=True)
            canny_input = mix
        except Exception:
            # Fallback to original if red-null fails
            canny_input = img
    else:
        canny_input = img

    # --- Edge detection (manual Canny only)
    edges = canny_edges(canny_input, t1=args.t1, t2=args.t2, sigma=args.sigma)
    print(f"Manual Canny thresholds: T1={int(args.t1)}, T2={int(args.t2)}")

    # --- Overlay or raw output
    show = overlay_edges(img, edges) if args.overlay else edges
    cv2.imshow("Canny Result", show)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    if args.out_path:
        cv2.imwrite(args.out_path, show)
        print(f"Saved: {args.out_path}")


if __name__ == "__main__":
    _cli()
