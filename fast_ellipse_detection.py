"""
Fast ellipse detection similar to LabVIEW IMAQ Detect Ellipses.
Uses findContours + fitEllipse without RANSAC for speed.
"""
import cv2
import numpy as np
import time
from typing import Tuple, List, Dict
from collections import deque

# Performance logging
_perf_log = deque(maxlen=500)  # Store last 500 frame timings
_log_enabled = False
_log_start_time = None


def start_performance_log():
    """Start performance logging."""
    global _log_enabled, _log_start_time, _perf_log
    _perf_log.clear()
    _log_enabled = True
    _log_start_time = time.time()
    print("[Fast Ellipse] Performance logging STARTED")


def stop_performance_log():
    """Stop logging and print analysis."""
    global _log_enabled
    _log_enabled = False

    if not _perf_log:
        print("[Fast Ellipse] No data collected")
        return

    print("\n" + "=" * 70)
    print("FAST ELLIPSE DETECTION - PERFORMANCE LOG")
    print("=" * 70)

    times = [entry['total_ms'] for entry in _perf_log]
    contour_counts = [entry['contours'] for entry in _perf_log]
    detection_counts = [entry['detections'] for entry in _perf_log]

    avg_ms = sum(times) / len(times)
    max_ms = max(times)
    min_ms = min(times)

    print(f"Total frames: {len(times)}")
    print(f"Average time: {avg_ms:.2f}ms")
    print(f"Min time: {min_ms:.2f}ms")
    print(f"Max time: {max_ms:.2f}ms")
    print(f"Average contours: {sum(contour_counts)/len(contour_counts):.1f}")
    print(f"Max contours: {max(contour_counts)}")
    print(f"Average detections: {sum(detection_counts)/len(detection_counts):.1f}")

    # Find slow frames (> 10ms)
    slow_frames = [(i, e) for i, e in enumerate(_perf_log) if e['total_ms'] > 10]
    if slow_frames:
        print(f"\n⚠️ SLOW FRAMES (>10ms): {len(slow_frames)}")
        print("-" * 70)
        for i, entry in slow_frames[:10]:  # Show first 10
            print(f"  Frame {i}: {entry['total_ms']:.1f}ms | contours: {entry['contours']} | detections: {entry['detections']} | fitEllipse: {entry['fit_count']}")
    else:
        print("\n✅ No slow frames detected!")

    # Analyze correlation between contours and time
    print("\n" + "-" * 70)
    print("CONTOUR COUNT vs TIME:")
    bins = [(0, 10), (10, 50), (50, 100), (100, 200), (200, 500), (500, 10000)]
    for low, high in bins:
        frames_in_bin = [e for e in _perf_log if low <= e['contours'] < high]
        if frames_in_bin:
            avg_t = sum(e['total_ms'] for e in frames_in_bin) / len(frames_in_bin)
            print(f"  Contours {low:4}-{high:4}: {len(frames_in_bin):3} frames, avg {avg_t:.2f}ms")

    print("=" * 70 + "\n")


def detect_ellipses_fast(
    edges: np.ndarray,
    original_bgr: np.ndarray,
    min_radius: int = 25,
    max_radius: int = 200,
    min_points: int = 5,
    max_aspect_ratio: float = 1.5,  # How circular (1.0 = perfect circle)
    min_circularity: float = 0.5,   # Contour circularity filter
) -> Tuple[np.ndarray, List[Dict]]:
    """
    Fast ellipse detection using contour analysis.
    Similar to LabVIEW IMAQ Detect Ellipses.

    Args:
        edges: Binary edge image (from Canny)
        original_bgr: Original BGR frame for drawing
        min_radius: Minimum ellipse radius (default 25 like LabVIEW)
        max_radius: Maximum ellipse radius (default 200 like LabVIEW)
        min_points: Minimum contour points for fitEllipse (must be >= 5)
        max_aspect_ratio: Maximum ratio of major/minor axis (1.5 = near circular)
        min_circularity: Minimum contour circularity (0-1, higher = more circular)

    Returns:
        Tuple of (overlay_frame, list_of_detections)
    """
    global _log_enabled, _perf_log

    t_start = time.perf_counter() if _log_enabled else 0
    fit_ellipse_count = 0
    contour_count = 0

    if edges is None or original_bgr is None:
        return original_bgr, []

    # Ensure binary image
    if edges.dtype != np.uint8:
        edges = edges.astype(np.uint8)

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour_count = len(contours) if contours else 0

    if not contours:
        if _log_enabled:
            _perf_log.append({
                'total_ms': (time.perf_counter() - t_start) * 1000,
                'contours': 0,
                'detections': 0,
                'fit_count': 0,
            })
        return original_bgr, []

    # Pre-calculate area limits
    min_area = np.pi * (min_radius ** 2) * 0.5  # Allow some tolerance
    max_area = np.pi * (max_radius ** 2) * 1.5

    detections = []
    overlay = None  # Lazy copy - only if we have detections

    for contour in contours:
        # Quick filters first (fast rejection)
        n_points = len(contour)
        if n_points < min_points:
            continue

        # Area filter
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue

        # Circularity filter (fast approximation)
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        circularity = 4.0 * np.pi * area / (perimeter * perimeter)
        if circularity < min_circularity:
            continue

        # Fit ellipse (requires at least 5 points)
        fit_ellipse_count += 1
        try:
            ellipse = cv2.fitEllipse(contour)
        except cv2.error:
            continue

        (cx, cy), (width, height), angle = ellipse

        # Validate ellipse parameters
        if width <= 0 or height <= 0:
            continue
        if not np.isfinite(cx) or not np.isfinite(cy):
            continue

        # Calculate radii
        major = max(width, height)
        minor = min(width, height)
        r_major = major / 2.0
        r_minor = minor / 2.0

        # Radius filter
        if r_major < min_radius or r_major > max_radius:
            continue
        if r_minor < min_radius * 0.5:  # Minor can be smaller
            continue

        # Aspect ratio filter (how circular)
        if r_minor > 0:
            aspect = r_major / r_minor
            if aspect > max_aspect_ratio:
                continue
        else:
            continue

        # Valid detection - create overlay if needed
        if overlay is None:
            overlay = original_bgr.copy()

        # Draw ellipse
        center = (int(round(cx)), int(round(cy)))
        axes = (int(round(major / 2)), int(round(minor / 2)))
        cv2.ellipse(overlay, center, axes, angle, 0, 360, (0, 255, 0), 2)
        cv2.circle(overlay, center, 3, (0, 0, 255), -1)

        detections.append({
            'center': {'x': float(cx), 'y': float(cy)},
            'axes': {'major': float(major), 'minor': float(minor)},
            'angle': float(angle),
            'area': float(area),
            'aspect': float(aspect) if r_minor > 0 else 1.0,
            'radius_major': float(r_major),
            'radius_minor': float(r_minor),
        })

    # Return original if no detections
    if overlay is None:
        if _log_enabled:
            _perf_log.append({
                'total_ms': (time.perf_counter() - t_start) * 1000,
                'contours': contour_count,
                'detections': 0,
                'fit_count': fit_ellipse_count,
            })
        return original_bgr, []

    # Log performance
    if _log_enabled:
        _perf_log.append({
            'total_ms': (time.perf_counter() - t_start) * 1000,
            'contours': contour_count,
            'detections': len(detections),
            'fit_count': fit_ellipse_count,
        })

    return overlay, detections


def detect_circles_fast(
    edges: np.ndarray,
    original_bgr: np.ndarray,
    min_radius: int = 25,
    max_radius: int = 200,
) -> Tuple[np.ndarray, List[Dict]]:
    """
    Fast circle detection - only detects near-perfect circles.
    Uses stricter aspect ratio filter.
    """
    return detect_ellipses_fast(
        edges,
        original_bgr,
        min_radius=min_radius,
        max_radius=max_radius,
        min_points=5,
        max_aspect_ratio=1.3,  # Stricter - more circular
        min_circularity=0.6,   # Stricter - rounder contours
    )

