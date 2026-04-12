import cv2
import numpy as np
import time
import os
from datetime import datetime
from collections import deque

from red_nuling_preprocessing import keep_only_red, get_red_null_params
from canny_edge import canny_edges, overlay_edges
from ellipse_detection import detect_ellipses

# GPU processing (with CPU fallback)
try:
    from gpu_processing import get_gpu_processor, is_gpu_available
    GPU_AVAILABLE = is_gpu_available()
except Exception as e:
    print(f"[ImageProcessor] GPU module not available: {e}")
    GPU_AVAILABLE = False

# Fast ellipse detection (LabVIEW-style - much faster than HoughCircles)
FAST_ELLIPSE_AVAILABLE = False
detect_ellipses_fast = None
try:
    from fast_ellipse_detection import detect_ellipses_fast
    FAST_ELLIPSE_AVAILABLE = True
    print("[ImageProcessor] Fast ellipse detection ENABLED (LabVIEW-style)")
except Exception as e:
    print(f"[ImageProcessor] Fast ellipse module not available: {e}")

# Optional weather detection (non-fatal)
try:
    from qt_weather_detection import get_weather
    WEATHER_DETECTION_AVAILABLE = True
except Exception:
    def get_weather(bgr, mode='auto'):
        return None
    WEATHER_DETECTION_AVAILABLE = False

try:
    import psutil
except Exception:
    psutil = None
try:
    import pynvml
    pynvml.nvmlInit()
    _nvml_available = True
except Exception:
    pynvml = None
    _nvml_available = False

# ===== PERFORMANCE LOGGING =====
_process_log = deque(maxlen=1000)
_system_log = deque(maxlen=1000)
_log_enabled = False
_vehicle_speed = None  # current vehicle speed (set from GUI)


def log_system_metrics(fps: float, cpu_percent: float, gpu_percent: float = None, gpu_mem_mb: float = None):
    """Log system metrics (called externally each frame when available).

    gpu_percent: device utilization percent (0-100) for the GPU as a whole —
    recorded only when the process actually uses the GPU; otherwise 0 or None.
    """
    if not _log_enabled:
        return
    _system_log.append({
        'fps': fps,
        'cpu': cpu_percent,
        'gpu': gpu_percent,
        'gpu_mem_mb': gpu_mem_mb
    })


def start_process_log():
    """Start full process logging."""
    global _log_enabled, _process_log, _system_log
    _process_log.clear()
    _system_log.clear()
    _log_enabled = True
    print("[Process Log] Started - tracking Red, Canny, Ellipse, ReadSign times")


def stop_process_log():
    """Stop logging and save analysis to file."""
    global _log_enabled
    _log_enabled = False

    if not _process_log:
        print("[Process Log] No data collected")
        return

    # Copy data to avoid modification during processing
    process_data = list(_process_log)
    system_data = list(_system_log)

    # Create log_files directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(__file__), "log_files")
    os.makedirs(log_dir, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(log_dir, f"perf_log_{timestamp}.txt")

    # Build log content
    lines = []
    lines.append("=" * 80)
    lines.append("FULL PROCESS PIPELINE - PERFORMANCE LOG")
    lines.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    lines.append(f"Total frames: {len(process_data)}")
    lines.append("-" * 80)

    # Calculate averages
    def avg(key):
        vals = [e[key] for e in process_data if e.get(key) is not None]
        return sum(vals) / len(vals) if vals else 0

    def max_val(key):
        vals = [e[key] for e in process_data if e.get(key) is not None]
        return max(vals) if vals else 0

    lines.append(f"{'Stage':<20} | {'Avg (ms)':>10} | {'Max (ms)':>10}")
    lines.append("-" * 50)
    lines.append(f"{'Red Nulling':<20} | {avg('red_ms'):>10.2f} | {max_val('red_ms'):>10.2f}")
    lines.append(f"{'Canny':<20} | {avg('canny_ms'):>10.2f} | {max_val('canny_ms'):>10.2f}")
    lines.append(f"{'Ellipse Detection':<20} | {avg('ellipse_ms'):>10.2f} | {max_val('ellipse_ms'):>10.2f}")
    lines.append(f"{'Read Sign (total)':<20} | {avg('read_sign_ms'):>10.2f} | {max_val('read_sign_ms'):>10.2f}")
    lines.append(f"{'TOTAL':<20} | {avg('total_ms'):>10.2f} | {max_val('total_ms'):>10.2f}")
    lines.append("-" * 80)

    # ===== SYSTEM METRICS (CPU, GPU, FPS) =====
    if system_data:
        lines.append("\n" + "=" * 80)
        lines.append("SYSTEM METRICS (CPU, GPU, FPS)")
        lines.append("=" * 80)

        def avg_sys(key):
            vals = [e[key] for e in system_data if e.get(key) is not None]
            return sum(vals) / len(vals) if vals else 0

        def min_sys(key):
            vals = [e[key] for e in system_data if e.get(key) is not None]
            return min(vals) if vals else 0

        def max_sys(key):
            vals = [e[key] for e in system_data if e.get(key) is not None]
            return max(vals) if vals else 0

        lines.append(f"{'Metric':<20} | {'Avg':>10} | {'Min':>10} | {'Max':>10}")
        lines.append("-" * 60)
        lines.append(f"{'FPS':<20} | {avg_sys('fps'):>10.1f} | {min_sys('fps'):>10.1f} | {max_sys('fps'):>10.1f}")
        lines.append(f"{'App CPU %':<20} | {avg_sys('cpu'):>10.1f} | {min_sys('cpu'):>10.1f} | {max_sys('cpu'):>10.1f}")

        if any(e.get('gpu') is not None for e in system_data):
            lines.append(f"{'GPU Util %':<20} | {avg_sys('gpu'):>10.1f} | {min_sys('gpu'):>10.1f} | {max_sys('gpu'):>10.1f}")

        lines.append("-" * 80)

    # Find slow frames
    slow_frames = [e for e in process_data if e.get('total_ms', 0) > 16]  # > 16ms = < 60 FPS
    if slow_frames:
        lines.append(f"\n⚠️ SLOW FRAMES (>16ms = <60 FPS): {len(slow_frames)} ({100*len(slow_frames)/len(process_data):.1f}%)")
        lines.append("-" * 80)

        # Analyze what causes slow frames
        slow_by_read_sign = [e for e in slow_frames if e.get('read_sign_ms') and e['read_sign_ms'] > 5]
        slow_by_ellipse = [e for e in slow_frames if e.get('ellipse_ms') and e['ellipse_ms'] > 5]
        slow_by_red = [e for e in slow_frames if e.get('red_ms') and e['red_ms'] > 5]

        lines.append(f"  Slow due to Read Sign (>5ms): {len(slow_by_read_sign)}")
        lines.append(f"  Slow due to Ellipse (>5ms):   {len(slow_by_ellipse)}")
        lines.append(f"  Slow due to Red Nulling (>5ms): {len(slow_by_red)}")

        # Show worst frames
        lines.append("\n  Top 10 slowest frames:")
        sorted_slow = sorted(slow_frames, key=lambda x: x.get('total_ms', 0), reverse=True)[:10]
        for i, e in enumerate(sorted_slow):
            lines.append(f"    {i+1}. Total: {e.get('total_ms',0):.1f}ms | Red: {e.get('red_ms',0):.1f} | Canny: {e.get('canny_ms',0):.1f} | Ellipse: {e.get('ellipse_ms',0):.1f} | ReadSign: {e.get('read_sign_ms',0):.1f}ms ({e.get('read_sign_count',0)})")

        lines.append("\n")

    # ===== WEATHER SUMMARY =====
    weather_list = [e.get('weather') for e in process_data if 'weather' in e]
    if weather_list:
        from collections import Counter
        cnt = Counter([w if w is not None else 'unknown' for w in weather_list])
        lines.append("\n" + "=" * 80)
        lines.append("WEATHER SUMMARY")
        lines.append("=" * 80)
        for k, v in cnt.items():
            lines.append(f"{k}: {v} frames ({100.0*v/len(weather_list):.1f}%)")
        lines.append("-" * 80)

    # ===== RED-NULL PARAMS SUMMARY =====
    # Find the most recent non-empty rn_params recorded in process_data (if any)
    rn_examples = [e.get('rn_params') for e in process_data if e.get('rn_params')]
    if rn_examples:
        # use the last recorded rn_params as representative
        last_rn = rn_examples[-1]
        lines.append("\n" + "=" * 80)
        lines.append("RED-NULL PARAMETERS (representative / last seen)")
        lines.append("=" * 80)
        lines.append(f"rd: {last_rn.get('rd')}")
        lines.append(f"min_brightness: {last_rn.get('min_brightness')}")
        lines.append(f"brightness: {last_rn.get('brightness')}")
        lines.append(f"contrast: {last_rn.get('contrast')}")
        lines.append(f"pre_blur_ksize: {last_rn.get('pre_blur_ksize')}")
        lines.append("-" * 80)

    # Include Red-Null parameter summary and raw data for ALL frames (process + system metrics + weather)
    lines.append("\n" + "=" * 80)
    lines.append(f"RAW DATA (all {len(process_data)} frames):")
    lines.append("-" * 80)
    # Include RN param columns too
    lines.append("Frame | Total | Red  | Canny | Ellipse | ReadSign | Detections | DetSpeed | VehSpeed | Weather | RN_RD  | RN_MIN_B | RN_BRI  | RN_CON  | RN_BLUR | FPS   | CPU  | GPU%  | GPU_MB")

    # Compute average system metrics to use in the SUMMARY only (do not use to fill per-frame rows)
    avg_sys_cpu = None
    avg_sys_gpu = None
    avg_sys_fps = None
    if system_data:
        # Only consider positive (non-zero) samples as valid for summary
        cpu_vals = [sd.get('cpu') for sd in system_data if sd.get('cpu') is not None and sd.get('cpu') > 0]
        gpu_vals = [sd.get('gpu') for sd in system_data if sd.get('gpu') is not None and sd.get('gpu') > 0]
        fps_vals = [sd.get('fps') for sd in system_data if sd.get('fps') is not None and sd.get('fps') > 0]
        if cpu_vals:
            try:
                avg_sys_cpu = sum(cpu_vals) / len(cpu_vals)
            except Exception:
                avg_sys_cpu = None
        if gpu_vals:
            try:
                avg_sys_gpu = sum(gpu_vals) / len(gpu_vals)
            except Exception:
                avg_sys_gpu = None
        if fps_vals:
            try:
                avg_sys_fps = sum(fps_vals) / len(fps_vals)
            except Exception:
                avg_sys_fps = None

    # Prepare per-frame raw rows: use only real system samples (indexed by time when recorded),
    # do NOT fill missing values with averages or repeat last sample — show '--' instead.
    for i, e in enumerate(_process_log):
        total_ms = e.get('total_ms') or 0
        red_ms = e.get('red_ms') or 0
        canny_ms = e.get('canny_ms') or 0
        ellipse_ms = e.get('ellipse_ms') or 0
        read_sign_ms = e.get('read_sign_ms') or 0
        detections = e.get('read_sign_count', 0)
        detected_speed_val = e.get('detected_speed') if e.get('detected_speed') is not None else 0
        veh_speed_val = e.get('vehicle_speed') if e.get('vehicle_speed') is not None else 0
        weather_val = e.get('weather') if e.get('weather') is not None else 'unknown'

        # Red-null params for this frame (if any)
        rn = e.get('rn_params') or {}
        rn_rd = rn.get('rd') if rn else None
        rn_min_b = rn.get('min_brightness') if rn else None
        rn_bri = rn.get('brightness') if rn else None
        rn_con = rn.get('contrast') if rn else None
        rn_blur = rn.get('pre_blur_ksize') if rn else None

        # Use system_data entry for the same index if available — treated as the real per-frame sample
        fps_val = None
        cpu_val = None
        gpu_val = None
        sd = None
        if i < len(system_data):
            sd = system_data[i]
            sfps = sd.get('fps')
            if sfps is not None and sfps > 0:
                fps_val = sfps
            scpu = sd.get('cpu')
            if scpu is not None and scpu > 0:
                cpu_val = scpu
            sgpu = sd.get('gpu')
            if sgpu is not None and sgpu > 0:
                gpu_val = sgpu

        # Format strings: show measured values when present, otherwise a clear placeholder
        fps_s = f"{fps_val:5.1f}" if fps_val is not None else "  -- "
        cpu_s = f"{cpu_val:4.1f}" if cpu_val is not None else " -- "
        gpu_val = sd.get('gpu') if i < len(system_data) else None
        gpu_s = f"{gpu_val:5.1f}" if (gpu_val is not None and gpu_val > 0) else " 0.0"
        gpu_mb_val = None
        if sd is not None:
            gm = sd.get('gpu_mem_mb')
            if gm is not None and gm > 0:
                gpu_mb_val = gm

        gpu_mb_s = f"{gpu_mb_val:6.0f}" if gpu_mb_val is not None else "  -- "

        # Format RN values with placeholders
        rn_rd_s = f"{rn_rd:.2f}" if (rn_rd is not None) else " -- "
        rn_min_b_s = f"{rn_min_b:3d}" if (rn_min_b is not None) else " -- "
        rn_bri_s = f"{rn_bri:4d}" if (rn_bri is not None) else " -- "
        rn_con_s = f"{rn_con:.2f}" if (rn_con is not None) else " -- "
        rn_blur_s = f"{rn_blur:2d}" if (rn_blur is not None) else " -- "

        lines.append(f"{i:5} | {total_ms:5.1f} | {red_ms:4.1f} | {canny_ms:5.1f} | {ellipse_ms:7.1f} | {read_sign_ms:8.1f} | {detections:10} | {detected_speed_val:7.1f} | {veh_speed_val:7.1f} | {weather_val:7} | {rn_rd_s:6} | {rn_min_b_s:8} | {rn_bri_s:7} | {rn_con_s:7} | {rn_blur_s:7} | {fps_s} | {cpu_s} | {gpu_s}| {gpu_mb_s}")

    lines.append("=" * 80)

    # Write to file
    content = "\n".join(lines)
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n📁 Log saved to: {log_file}")


class ImageProcessor:
    def __init__(self):
        self.enable_red = False
        self.enable_canny = False
        self.enable_ellipse = False

        # runtime override parameters for red nulling (set by GUI dialog)
        # when None, weather-based defaults will be used
        self.rn_params = None

        # GPU processor
        self.use_gpu = GPU_AVAILABLE
        if self.use_gpu:
            self.gpu = get_gpu_processor()
            print("[ImageProcessor] GPU acceleration ENABLED")
        else:
            self.gpu = None
            print("[ImageProcessor] GPU acceleration DISABLED (using CPU)")

        # Fast ellipse detection (LabVIEW-style, ~1ms instead of ~30ms)
        self.use_fast_ellipse = FAST_ELLIPSE_AVAILABLE
        if self.use_fast_ellipse:
            print("[ImageProcessor] Fast ellipse detection ENABLED")
        else:
            print("[ImageProcessor] Fast ellipse detection DISABLED (using fallback)")

        # injected from GUI
        self.ellipse_saver = None
        self.speed_reader = None
        self.last_speed = None
        self.read_sign_enabled = False

        # Detection state for current frame
        self.sign_detected_this_frame = False

        # weather tracking
        self.last_weather = None

        # ROI hit state for UI overlay (per-frame)
        self.last_roi_hits = [False, False]
        self.last_sign_center = None

        # Pre-allocated output buffer for red nulling.
        # Avoids np.zeros_like every frame (eliminates ~0.3ms malloc + GC jitter).
        # Resized automatically when frame dimensions change.
        self._work2_buf: np.ndarray | None = None
        self._work2_shape: tuple | None = None

        # =========================
        # ROI SETTINGS (2 boxy namiesto GRID)
        # =========================
        # frakcie z obrazu (w,h) - doladíš podľa potreby
        self.roi_y1_frac = 0  # HD720  (720px):   0.00 * 720  = 0 px,   HD1080 (1080px):  0.00 * 1080 = 0 px
        self.roi_y2_frac = 1  # HD720  (720px):   0.65 * 720  = 468 px, HD1080 (1080px):  0.65 * 1080 = 702 px

        # ROI 1 (ľavá)
        self.roi1_x1_frac = 0 # HD720  (1280px): 0.00 * 1280 = 0 px, HD1080 (1920px): 0.00 * 1920 = 0 px
        self.roi1_x2_frac = 0.35 # HD720  (1280px): 0.35 * 1280 = 448 px, HD1080 (1920px): 0.35 * 1920 = 672 px

        # ROI 2 (pravá)
        self.roi2_x1_frac = 0.65 # HD720  (1280px): 0.65 * 1280 = 832 px, HD1080 (1920px): 0.65 * 1920 = 1248 px
        self.roi2_x2_frac = 1 # HD720  (1280px): 1.00 * 1280 = 1280 px, HD1080 (1920px): 1.00 * 1920 = 1920 px

    # =========================
    # TOGGLES
    # =========================
    def toggle_red(self):
        self.enable_red = not self.enable_red

    def toggle_canny(self):
        self.enable_canny = not self.enable_canny

    def toggle_ellipse(self):
        self.enable_ellipse = not self.enable_ellipse

    def get_rois(self, h: int, w: int):
        """Return list of ROI rectangles (x1,y1,x2,y2) in pixel coords."""
        y1 = int(h * self.roi_y1_frac)
        y2 = int(h * self.roi_y2_frac)

        y1 = max(0, min(y1, h - 2))
        y2 = max(y1 + 1, min(y2, h))

        r1x1 = int(w * self.roi1_x1_frac)
        r1x2 = int(w * self.roi1_x2_frac)
        r2x1 = int(w * self.roi2_x1_frac)
        r2x2 = int(w * self.roi2_x2_frac)

        r1x1 = max(0, min(r1x1, w - 2))
        r1x2 = max(r1x1 + 1, min(r1x2, w))
        r2x1 = max(0, min(r2x1, w - 2))
        r2x2 = max(r2x1 + 1, min(r2x2, w))

        return [(r1x1, y1, r1x2, y2), (r2x1, y1, r2x2, y2)]


    # =========================
    # PROCESS
    # =========================
    def process(self, frame_bgr: np.ndarray) -> np.ndarray:
        global _log_enabled, _process_log

        if frame_bgr is None:
            return frame_bgr

        # Update weather detection (throttled inside get_weather)
        try:
            weather = get_weather(frame_bgr)
            if weather is not None:
                self.last_weather = weather
        except Exception:
            pass

        # Fast path - if nothing is enabled, return original without copying
        if not self.enable_red and not self.enable_canny and not self.enable_ellipse:
            return frame_bgr

        # Timing variables
        t_start = time.perf_counter() if _log_enabled else 0
        red_ms = None
        canny_ms = None
        ellipse_ms = None
        read_sign_ms = None
        read_sign_count = 0

        # Keep reference to original for ellipse cropping (no copy yet)
        original = frame_bgr

        # reset ROI hits (for preview overlay)
        self.last_roi_hits = [False, False]
        self.last_sign_center = None
        work = frame_bgr
        edges = None

        # track which red-null params were used for this frame (None if not run)
        frame_rn_params = None

        # ===== ROI SETTINGS (2 boxy namiesto GRID) =====
        h0, w0 = work.shape[:2]
        rois = self.get_rois(h0, w0)


        if self.enable_red:
            t0 = time.perf_counter() if _log_enabled else 0

            # Get weather-based parameters
            try:
                params = get_red_null_params(getattr(self, 'last_weather', None))
            except Exception:
                params = {
                    'rd': 1.45,
                    'min_brightness': 10,
                    'brightness': 0,
                    'contrast': 1.0,
                    'pre_blur_ksize': 3,
                }

            # allow GUI runtime overrides
            if self.rn_params is not None:
                params = {**params, **(self.rn_params | {})}

            # remember params used for this frame for logging
            try:
                frame_rn_params = dict(params)
            except Exception:
                frame_rn_params = None

            # ---- TILE-BASED RED NULLING ----
            # Use pre-allocated buffer to avoid np.zeros_like every frame.
            if self._work2_buf is None or self._work2_shape != work.shape:
                self._work2_buf = np.zeros(work.shape, dtype=work.dtype)
                self._work2_shape = work.shape

            work2 = self._work2_buf

            # Zero only the ROI regions (not full frame — saves ~0.2ms)
            for (x1, y1, x2, y2) in rois:
                work2[y1:y2, x1:x2] = 0

            # Cache param lookups outside the loop
            _rd         = params.get('rd', 1.45)
            _min_b      = params.get('min_brightness', 10)
            _brightness = params.get('brightness', 0)
            _contrast   = params.get('contrast', 1.0)
            _blur       = params.get('pre_blur_ksize', 3)

            for (x1, y1, x2, y2) in rois:
                tile = work[y1:y2, x1:x2]

                if self.use_gpu and self.gpu is not None:
                    try:
                        work2[y1:y2, x1:x2] = self.gpu.red_nulling_gpu(
                            tile, rd=_rd, min_brightness=_min_b
                        )
                    except Exception:
                        work2[y1:y2, x1:x2] = keep_only_red(
                            tile, brightness=_brightness, contrast=_contrast,
                            rd=_rd, min_brightness=_min_b, pre_blur_ksize=_blur
                        )
                else:
                    work2[y1:y2, x1:x2] = keep_only_red(
                        tile, brightness=_brightness, contrast=_contrast,
                        rd=_rd, min_brightness=_min_b, pre_blur_ksize=_blur
                    )

            work = work2

            if _log_enabled:
                red_ms = (time.perf_counter() - t0) * 1000

        if self.enable_canny:
            t0 = time.perf_counter() if _log_enabled else 0

            edges_full = np.zeros((h0, w0), dtype=np.uint8)

            for (x1, y1, x2, y2) in rois:
                tile = work[y1:y2, x1:x2]

                if self.use_gpu and self.gpu is not None:
                    e_tile = self.gpu.canny_gpu(tile)
                else:
                    e_tile = canny_edges(tile)

                edges_full[y1:y2, x1:x2] = e_tile

            edges = edges_full

            if _log_enabled:
                canny_ms = (time.perf_counter() - t0) * 1000

        if self.enable_ellipse and edges is not None:
            t0 = time.perf_counter() if _log_enabled else 0
            # Use fast LabVIEW-style detection (~1ms vs ~30ms for HoughCircles)
            if self.use_fast_ellipse and detect_ellipses_fast is not None:
                out, ellipse_crops = detect_ellipses_fast(edges, original)
            else:
                out, ellipse_crops = detect_ellipses(edges, original)
            if _log_enabled:
                ellipse_ms = (time.perf_counter() - t0) * 1000

            # Process each detected ellipse
            t_read_start = time.perf_counter() if _log_enabled else 0

            # Determine which ROI contains detected ellipse center (for UI color switch)
            try:
                hh, ww = original.shape[:2]
                _rois = self.get_rois(hh, ww)
            except Exception:
                _rois = None

            for det in ellipse_crops:
                # Mark that we detected a sign in this frame
                self.sign_detected_this_frame = True

                cx = int(det['center']['x'])
                cy = int(det['center']['y'])
                major = int(det['axes']['major'])
                minor = int(det['axes']['minor'])

                # store sign center + ROI hit flags for UI
                try:
                    self.last_sign_center = (cx, cy, major // 2, minor // 2)
                    if _rois is not None:
                        for ridx, (x1, y1, x2, y2) in enumerate(_rois):
                            if x1 <= cx < x2 and y1 <= cy < y2:
                                if 0 <= ridx < len(self.last_roi_hits):
                                    self.last_roi_hits[ridx] = True
                except Exception:
                    pass

                # Use previously extracted major/minor
                half_w = major // 2
                half_h = minor // 2

                x1 = max(cx - half_w, 0)
                y1 = max(cy - half_h, 0)
                x2 = min(cx + half_w, original.shape[1])
                y2 = min(cy + half_h, original.shape[0])

                crop = original[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                # ==============================
                # SAVE ELLIPSES FROM ORIGINAL
                # ==============================
                if self.ellipse_saver is not None:
                    self.ellipse_saver.save(crop.copy())

                # =========================
                # READ SIGN (PERCEPTRON)
                # =========================
                if (
                        hasattr(self, "speed_reader")
                        and self.speed_reader is not None
                        and hasattr(self, "read_sign_enabled")
                        and self.read_sign_enabled
                ):
                    read_sign_count += 1
                    speed = self.speed_reader.predict_from_crop(crop)
                    if speed is not None:
                        self.last_speed = speed

            if _log_enabled:
                read_sign_ms = (time.perf_counter() - t_read_start) * 1000

            # Log this frame
            if _log_enabled:
                _process_log.append({
                    'total_ms': (time.perf_counter() - t_start) * 1000,
                    'red_ms': red_ms,
                    'canny_ms': canny_ms,
                    'ellipse_ms': ellipse_ms,
                    'read_sign_ms': read_sign_ms,
                    'read_sign_count': read_sign_count,
                    'detected_speed': getattr(self, 'last_speed', None),
                    'vehicle_speed': _vehicle_speed,
                    'weather': getattr(self, 'last_weather', None),
                    'rn_params': frame_rn_params,
                })

            return out

        # Log for non-ellipse paths
        if _log_enabled:
            _process_log.append({
                'total_ms': (time.perf_counter() - t_start) * 1000,
                'red_ms': red_ms,
                'canny_ms': canny_ms,
                'ellipse_ms': None,
                'read_sign_ms': None,
                'read_sign_count': 0,
                'detected_speed': getattr(self, 'last_speed', None),
                'vehicle_speed': _vehicle_speed,
                'weather': getattr(self, 'last_weather', None),
                'rn_params': frame_rn_params,
            })

        if self.enable_canny and edges is not None:
            return overlay_edges(work, edges)

        if self.enable_red:
            return work

        return original


def set_vehicle_speed(speed):
    """Set the current vehicle speed so it can be recorded in process logs."""
    global _vehicle_speed
    try:
        _vehicle_speed = float(speed) if speed is not None else None
    except Exception:
        _vehicle_speed = None
