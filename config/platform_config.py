"""
Cross-platform configuration helper.
Detects OS and hardware (Jetson vs Windows/Linux/Mac).
"""

import os
import platform as _platform
import sys

# Platform detection
SYSTEM = _platform.system()  # 'Windows', 'Linux', 'Darwin'
IS_WINDOWS = SYSTEM == "Windows"
IS_LINUX = SYSTEM == "Linux"
IS_MAC = SYSTEM == "Darwin"

# Jetson detection
IS_JETSON = False
JETSON_MODEL = None

if IS_LINUX:
    try:
        with open("/etc/nv_tegra_release", "r") as f:
            content = f.read()
            IS_JETSON = True
            # Parse model from file
            for line in content.split('\n'):
                if 'JETSON' in line.upper():
                    JETSON_MODEL = line.strip()
                    break
    except FileNotFoundError:
        IS_JETSON = False

# Derived information
SYSTEM_NAME = "Jetson Orin Nano" if IS_JETSON else SYSTEM
HAS_CUDA = False  # Will be set by GPU detection

# Serial port configuration
def get_serial_port(default_device=None):
    """Get appropriate serial port for platform."""
    if default_device:
        return default_device

    if IS_JETSON or IS_LINUX:
        return "/dev/ttyUSB0"  # Linux/Jetson default
    elif IS_WINDOWS:
        return "COM12"  # Windows default
    else:
        return "/dev/cu.usbserial"  # macOS default

# Audio backend
def has_winsound():
    """Check if winsound is available (Windows only)."""
    return IS_WINDOWS

# Path handling
def get_project_root():
    """Get project root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_asset_path(relative_path):
    """Get path to asset relative to project root."""
    return os.path.join(get_project_root(), relative_path)

# Model handling
def get_model_path(base_name="best"):
    """Get model path (quantized on Jetson if available)."""
    root = get_project_root()

    if IS_JETSON:
        quantized = os.path.join(root, "dataset", f"{base_name}_int8.pt")
        if os.path.exists(quantized):
            return quantized

    return os.path.join(root, "dataset", f"{base_name}.pt")

# Performance settings
def get_optimal_image_resolution():
    """Get optimal image resolution for platform."""
    if IS_JETSON:
        return (1280, 720)  # Better for Nano's limited GPU
    else:
        return (1920, 1080)  # Full HD for desktop

def get_optimal_fps():
    """Get optimal FPS for platform."""
    if IS_JETSON:
        return 15  # Conservative for Nano
    else:
        return 30  # Full speed for desktop

# Debug info
def print_system_info():
    """Print system information."""
    print(f"[System] OS: {SYSTEM_NAME}")
    print(f"[System] Python: {sys.version.split()[0]}")
    if IS_JETSON:
        print(f"[System] Jetson Model: {JETSON_MODEL}")
    print(f"[System] Platform: {_platform.platform()}")

if __name__ == "__main__":
    print_system_info()

