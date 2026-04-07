import pyrealsense2 as rs
import numpy as np
import cv2


class RealSenseCamera:
    """Intel RealSense D415 color-stream wrapper.

    - Returns frames as BGR (OpenCV compatible)
    - Start/stop lifecycle
    """

    def __init__(self, width=1920, height=1080, fps=30, auto_exposure=True, timeout_ms=5000):
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)
        self.auto_exposure = bool(auto_exposure)
        self.timeout_ms = int(timeout_ms)

        self.pipe = None
        self.cfg = None
        self.profile = None
        self.color_sensor = None
        self._fmt = None  # selected rs.format for color stream

    def start(self):
        """Start the color stream.

        NOTE:
        Some RealSense setups/drivers don't accept rs.format.bgr8 for the selected mode.
        We try multiple common formats and convert to BGR in read().
        """
        self.pipe = rs.pipeline()
        self.cfg = rs.config()

        last_err = None
        # Try formats in order of preference.
        for fmt in (rs.format.bgr8, rs.format.rgb8, rs.format.yuyv):
            try:
                self.cfg.disable_all_streams()
            except Exception:
                pass
            try:
                self.cfg.enable_stream(rs.stream.color, self.width, self.height, fmt, self.fps)
                self.profile = self.pipe.start(self.cfg)
                self._fmt = fmt
                last_err = None
                break
            except Exception as e:
                last_err = e
                # Make sure pipeline is stopped before retrying
                try:
                    self.pipe.stop()
                except Exception:
                    pass
                self.profile = None

        if self.profile is None:
            raise RuntimeError(
                f"RealSense: failed to start color stream ({self.width}x{self.height}@{self.fps}). Last error: {last_err}"
            )

        # Find color sensor robustly
        dev = self.profile.get_device()
        sensors = dev.query_sensors()

        self.color_sensor = None
        for s in sensors:
            try:
                name = s.get_info(rs.camera_info.name)
            except Exception:
                name = ""
            if "RGB" in name or "Color" in name:
                self.color_sensor = s
                break

        # Apply auto-exposure if available
        if self.color_sensor is not None:
            try:
                self.color_sensor.set_option(rs.option.enable_auto_exposure, 1 if self.auto_exposure else 0)
            except Exception:
                pass

        return True

    def set_auto_exposure(self, enabled: bool):
        """Enable/disable auto exposure during streaming (safe no-op if unsupported)."""
        self.auto_exposure = bool(enabled)
        if self.color_sensor is None:
            return
        try:
            import pyrealsense2 as rs
            self.color_sensor.set_option(rs.option.enable_auto_exposure, 1 if enabled else 0)
        except Exception:
            pass

    def read(self):
        """Return (ok, frame_bgr)."""
        if self.pipe is None:
            return False, None

        try:
            frames = self.pipe.wait_for_frames(self.timeout_ms)
            color_frame = frames.get_color_frame()
            if not color_frame:
                return False, None

            img = np.asanyarray(color_frame.get_data())

            # Convert to BGR for OpenCV
            if self._fmt == rs.format.bgr8:
                bgr = img
            elif self._fmt == rs.format.rgb8:
                bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            elif self._fmt == rs.format.yuyv:
                bgr = cv2.cvtColor(img, cv2.COLOR_YUV2BGR_YUY2)
            else:
                bgr = img

            return True, bgr
        except Exception:
            return False, None

    def stop(self):
        try:
            if self.pipe is not None:
                self.pipe.stop()
        finally:
            self.pipe = None
            self.cfg = None
            self.profile = None
            self.color_sensor = None
            self._fmt = None


# ======================================================
# Helpers: enumerate REAL color modes from the connected camera
# - used by gui.py InfoPanel so the resolution dropdown matches
#   what the RealSense actually reports.
# ======================================================

def list_realsense_color_modes(max_modes: int = 16):
    """Return a list like: ["1920x1080 @ 30", ...]

    Safe behavior:
    - If no device / no color sensor exists, returns [].
    - Filters to bgr8/rgb8/yuyv to avoid depth/infra.
    """
    try:
        ctx = rs.context()
        devs = ctx.query_devices()
        if devs.size() == 0:
            return []

        dev = devs[0]
        sensors = dev.query_sensors()

        color_sensor = None
        for s in sensors:
            try:
                name = s.get_info(rs.camera_info.name)
            except Exception:
                name = ""
            if "RGB" in name or "Color" in name:
                color_sensor = s
                break
        if color_sensor is None:
            return []

        modes = set()
        for sp in color_sensor.get_stream_profiles():
            try:
                v = sp.as_video_stream_profile()
                w = int(v.width())
                h = int(v.height())
                fps = int(v.fps())
                fmt = v.format()
                if fmt not in (rs.format.bgr8, rs.format.rgb8, rs.format.yuyv):
                    continue
                modes.add((w, h, fps))
            except Exception:
                continue

        modes = sorted(modes, key=lambda t: (t[0] * t[1], t[2]), reverse=True)
        if max_modes and len(modes) > int(max_modes):
            modes = modes[: int(max_modes)]

        return [f"{w}x{h} @ {fps}" for (w, h, fps) in modes]
    except Exception:
        return []
