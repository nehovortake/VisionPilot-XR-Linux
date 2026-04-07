from __future__ import annotations

import os
import platform
from pathlib import Path


def get_project_root() -> Path:
    env_root = os.environ.get("VISIONPILOT_XR_ROOT", "").strip()
    if env_root:
        p = Path(env_root).expanduser().resolve()
        if p.exists():
            return p
    return Path(__file__).resolve().parent


def project_path(*parts: str) -> Path:
    return get_project_root().joinpath(*parts)


def dataset_root() -> Path:
    return project_path("dataset")


def detections_root() -> Path:
    return project_path("detections")


def log_root() -> Path:
    return project_path("log_files")


def sign_icon_dir() -> Path:
    return project_path("gui_assets", "signstocluster")


def is_linux() -> bool:
    return platform.system().lower() == "linux"


def is_jetson() -> bool:
    if not is_linux():
        return False

    model_paths = [
        "/proc/device-tree/model",
        "/sys/firmware/devicetree/base/model",
    ]
    for p in model_paths:
        try:
            txt = Path(p).read_text(errors="ignore").lower()
            if "jetson" in txt or "orin" in txt or "tegra" in txt:
                return True
        except Exception:
            pass

    try:
        txt = Path("/etc/nv_tegra_release").read_text(errors="ignore").lower()
        if txt:
            return True
    except Exception:
        pass

    return False


def read_jetson_gpu_percent() -> float | None:
    candidates = [
        "/sys/class/devfreq/17000000.ga10b/load",
        "/sys/class/devfreq/17000000.gv11b/load",
        "/sys/devices/17000000.ga10b/devfreq/17000000.ga10b/load",
        "/sys/devices/17000000.gv11b/devfreq/17000000.gv11b/load",
        "/sys/devices/gpu.0/load",
    ]
    for p in candidates:
        try:
            raw = Path(p).read_text().strip()
            if not raw:
                continue
            val = float(raw)
            if val > 100.0:
                val = val / 10.0
            return max(0.0, min(100.0, val))
        except Exception:
            pass
    return None
