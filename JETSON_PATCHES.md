# Jetson-compatible patches pre VisionPilot XR

## PATCH 1: gpu_processing.py - Device name handling

BEFORE:
```python
print(f"[GPU Processing] CUDA Device: {torch.cuda.get_device_name(0)}")
```

AFTER:
```python
try:
    device_name = torch.cuda.get_device_name(0)
except Exception:
    device_name = "Unknown GPU"
print(f"[GPU Processing] CUDA Device: {device_name}")
```

---

## PATCH 2: gui.py - Platform detection at imports

ADD at line ~15 (after imports):

```python
import platform

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_JETSON = IS_LINUX and os.path.exists("/etc/nv_tegra_release")

# Conditional winsound import
try:
    if IS_WINDOWS:
        import winsound as _winsound
    else:
        _winsound = None
except Exception:
    _winsound = None
```

REPLACE the existing winsound import.

---

## PATCH 3: gui.py - Serial port configuration

In BackgroundWindow.__init__, change:

BEFORE:
```python
self._elm_port = "COM12"
self._elm_baud = 9600
```

AFTER:
```python
# Auto-detect serial port based on platform
if IS_JETSON or IS_LINUX:
    self._elm_port = "/dev/ttyUSB0"  # Linux/Jetson
elif IS_WINDOWS:
    self._elm_port = "COM12"  # Windows
else:
    self._elm_port = "/dev/cu.usbserial"  # macOS
self._elm_baud = 9600
```

---

## PATCH 4: qt_read_sign.py - Model path handling (if exists)

ADD at top of file after imports:

```python
import os
import platform

# Check if running on Jetson
IS_JETSON = os.path.exists("/etc/nv_tegra_release")

# Select appropriate model
if IS_JETSON:
    # Use quantized model on Jetson (if available)
    DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "dataset", "best_int8.pt")
    if not os.path.exists(DEFAULT_MODEL_PATH):
        DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "dataset", "best.pt")
else:
    DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "dataset", "best.pt")
```

---

## PATCH 5: realsense.py - Add fallback for Jetson

Make sure realsense.py imports are optional:

```python
try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    print("[RealSense] pyrealsense2 not available (install: pip install pyrealsense2)")
    REALSENSE_AVAILABLE = False
    rs = None

# ... rest of code ...

class RealSenseCamera:
    def __init__(self, ...):
        if not REALSENSE_AVAILABLE:
            raise RuntimeError("RealSense SDK not installed")
        # ... rest of init ...
```

---

## PATCH 6: Create platform_config.py

File: `config/platform_config.py` (NEW)

```python
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
```

---

## PATCH 7: Update gui.py imports to use platform_config

At top of gui.py (after initial imports), ADD:

```python
try:
    from config.platform_config import (
        IS_JETSON, IS_WINDOWS, IS_LINUX,
        get_serial_port, has_winsound,
        get_asset_path, SYSTEM_NAME
    )
except ImportError:
    # Fallback if config module doesn't exist
    IS_JETSON = False
    IS_WINDOWS = platform.system() == "Windows"
    IS_LINUX = platform.system() == "Linux"
    SYSTEM_NAME = platform.system()
    
    def get_serial_port(default=None):
        if default:
            return default
        return "/dev/ttyUSB0" if IS_LINUX else ("COM12" if IS_WINDOWS else "/dev/cu.usbserial")
    
    def has_winsound():
        return IS_WINDOWS
    
    def get_asset_path(rel_path):
        return os.path.join(os.path.dirname(__file__), rel_path)
```

Then replace winsound import section with:

```python
# Optional Windows warning sound (overspeed)
try:
    if has_winsound():
        import winsound as _winsound
    else:
        _winsound = None
except Exception:
    _winsound = None
```

---

## PATCH 8: gui.py - Update serial port in BackgroundWindow

Change in `BackgroundWindow.__init__`:

```python
# BEFORE:
self._elm_port = "COM12"

# AFTER:
self._elm_port = get_serial_port("COM12")  # Auto-detect or use default
```

---

## INSTALLATION CHECKLIST

1. **Create directory structure:**
   ```bash
   mkdir -p config
   touch config/__init__.py
   ```

2. **Copy platform_config.py:**
   - Save PATCH 6 as `config/platform_config.py`

3. **Apply patches to existing files:**
   - Apply PATCH 1 to `gpu_processing.py`
   - Apply PATCH 2-3 to `gui.py`
   - Apply PATCH 4 to `qt_read_sign.py` (if needed)
   - Apply PATCH 5 to `realsense.py`

4. **Verify imports:**
   ```bash
   python3 -c "from config.platform_config import *; print('Config OK')"
   ```

5. **Test on target platform:**
   - Windows: `python gui.py`
   - Jetson: `python3 gui.py`

---

## QUICK START ON JETSON

```bash
# 1. SSH to Jetson
ssh ubuntu@jetson.local

# 2. Create venv
python3.11 -m venv ~/visionpilot
source ~/visionpilot/bin/activate

# 3. Install dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install opencv-python numpy scipy pyserial psutil PyQt5

# 4. Install RealSense
pip install pyrealsense2

# 5. Copy project
scp -r /path/to/VisionPilot-XR/* ubuntu@jetson.local:~/visionpilot/

# 6. Run
cd ~/visionpilot
python3 gui.py
```

**DONE! 🎉**

