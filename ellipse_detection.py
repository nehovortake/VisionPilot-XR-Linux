from __future__ import annotations

import cv2
import numpy as np
from typing import Tuple, List, Dict, Optional, Any


def fit_ellipse_ransac(points: np.ndarray, threshold: float = 2.0, max_trials: int = 100) -> Tuple[Any, bool]:
    """Fit ellipse robustly using RANSAC."""
    if len(points) < 5:
        return None, False

    best_inliers = []
    best_ellipse = None

    n_points = len(points)

    for _ in range(max_trials):
        # Randomly sample 5 points to fit ellipse
        sample_idx = np.random.choice(n_points, 5, replace=False)
        sample = points[sample_idx]
        try:
            ellipse = cv2.fitEllipse(sample)
        except cv2.error:
            continue
        (cx, cy), (w, h), angle = ellipse
        major = max(w, h) * 0.5
        minor = min(w, h) * 0.5
        if minor == 0:
            continue

        # Calculate distances of all points to fitted ellipse
        cos_angle = np.cos(np.deg2rad(angle))
        sin_angle = np.sin(np.deg2rad(angle))
        dx = points[:, 0] - cx
        dy = points[:, 1] - cy
        x_rot = dx * cos_angle + dy * sin_angle
        y_rot = -dx * sin_angle + dy * cos_angle
        distances = np.abs((x_rot / major) ** 2 + (y_rot / minor) ** 2 - 1)

        inliers = points[distances <= threshold]
        if len(inliers) > len(best_inliers):
            best_inliers = inliers
            best_ellipse = ellipse

    if best_ellipse is not None and len(best_inliers) >= 0.5 * n_points:
        return best_ellipse, True
    return None, False


def detect_ellipses(
    edges: np.ndarray,
    original_bgr: np.ndarray,
    min_radius: float = 15.0,
    max_radius: float = 600.0,
    roundness: float = 2.0,
    *,
    min_contour_points: int = 8,
    draw_color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
    morph_kernel: int = 3,
    min_circularity: float = 0.8,
    ransac_threshold: float = 0.05,
) -> Tuple[np.ndarray, List[Dict]]:

    if edges is None or original_bgr is None:
        return original_bgr.copy() if original_bgr is not None else None, []

    gray = edges if edges.ndim == 2 else cv2.cvtColor(edges, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    if morph_kernel > 1:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (morph_kernel, morph_kernel))
        bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, k, iterations=1)

    cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    overlay = original_bgr.copy()
    detections: List[Dict] = []

    min_area = np.pi * (float(min_radius) ** 2)
    max_area = np.pi * (float(max_radius) ** 2)

    for c in cnts:
        if len(c) < min_contour_points:
            continue
        area = cv2.contourArea(c)
        if area < min_area or area > max_area:
            continue
        peri = cv2.arcLength(c, True)
        if peri <= 0:
            continue
        circularity = 4.0 * np.pi * area / (peri * peri)
        if circularity < min_circularity:
            continue

        # RANSAC ellipse fit
        points = c.reshape(-1, 2).astype(np.float32)
        ellipse, ok = fit_ellipse_ransac(points, threshold=ransac_threshold)
        if not ok:
            continue

        (cx, cy), (w, h), angle = ellipse

        # ---- HARD NUMERIC VALIDATION ----
        if not np.isfinite(cx) or not np.isfinite(cy) or not np.isfinite(angle):
            continue

        if not np.isfinite(w) or not np.isfinite(h):
            continue

        if w <= 0 or h <= 0:
            continue

        major = max(w, h)
        minor = min(w, h)
        ra = major * 0.5
        rb = minor * 0.5
        if ra < float(min_radius) or ra > float(max_radius):
            continue
        if rb <= 0:
            continue
        ratio = ra / rb
        if ratio > float(roundness):
            continue

        ellipse_tuple = ((int(round(cx)), int(round(cy))), (int(round(major)), int(round(minor))), float(angle))
        cv2.ellipse(overlay, ellipse_tuple, draw_color, thickness)
        cv2.circle(overlay, (int(round(cx)), int(round(cy))), 2, (0, 0, 255), -1)
        detections.append({
            'center': {'x': float(cx), 'y': float(cy)},
            'axes': {'major': float(major), 'minor': float(minor)},
            'angle': float(angle),
            'area': float(area),
            'aspect': float(ratio),
            'radius_major': float(ra),
            'radius_minor': float(rb),
        })

    return overlay, detections

