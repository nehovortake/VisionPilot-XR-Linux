# VisionPilot XR - NVIDIA Jetson Orin Nano Setup Guide

## 1. OVERVIEW - AKO BUDEME UPRAVOVAŤ KÓD

Tvoj kód obsahuje nasledujúce kritické veci pre Jetson:

```
1. PyTorch + CUDA (gpu_processing.py)     → ARM64 ARM binaries
2. OpenCV (cv2)                            → CUDA-optimized version
3. RealSense SDK (realsense.py)            → Jetson-compatible version
4. PyQt5 (GUI)                             → ARM64 kompatibilné
5. PySerial (ELM327)                       → No changes needed
6. Torch models (qt_read_sign.py)          → Otestovať na Jetson
```

---

## 2. HARDWARE REQUIREMENTS

- **NVIDIA Jetson Orin Nano 8GB** (recommended) or Nano 4GB
- **Jetpack 6.0 or newer** (contains CUDA 12.2, cuDNN 8.9)
- **RealSense D435i camera** (compatible)
- **USB OBD-II adapter** (ELM327) on /dev/ttyUSB0
- **Heat sink + cooling** (important!)
- **25W+ power supply**

---

## 3. JETPACK INSTALLATION

### 3.1 Flash JetPack to Jetson (Windows PC)

1. Download **NVIDIA SDK Manager** → https://developer.nvidia.com/sdk-manager
2. Connect Jetson in Recovery Mode:
   ```bash
   # On Jetson, hold POWER+RESET, then release only POWER
   ```
3. Flash JetPack 6.0+ with:
   - Ubuntu 22.04 LTS
   - CUDA 12.2
   - cuDNN
   - TensorRT

### 3.2 Verify Installation on Jetson

```bash
# SSH into Jetson (default: ubuntu@jetson.local)
ssh ubuntu@jetson.local

# Check CUDA
nvcc --version
# Expected: CUDA release 12.2

# Check GPU
nvidia-smi
# Expected: NVIDIA Jetson Orin Nano

# Check package versions
apt list --installed | grep cuda
```

---

## 4. PYTHON ENVIRONMENT SETUP

### 4.1 Create Virtual Environment

```bash
# On Jetson
sudo apt update && sudo apt upgrade -y

# Install Python dev tools
sudo apt install -y python3.11-dev python3.11-venv

# Create venv
python3.11 -m venv ~/visionpilot
source ~/visionpilot/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### 4.2 Install Core Dependencies

```bash
# opencv-python (CPU version)
pip install opencv-python

# numpy + scipy
pip install numpy scipy

# PyQt5 (GUI)
sudo apt install -y python3-pyqt5
# OR
pip install PyQt5 PyQt5-sip

# PySerial (ELM327)
pip install pyserial

# System monitor
pip install psutil

# IDEs
pip install jupyter jupyter-lab
```

---

## 5. PYTORCH + CUDA SETUP (CRITICAL)

### 5.1 ARM64 PyTorch for Jetson Orin Nano

**ВАЖНО**: Normal `pip install torch` does NOT work for ARM64!
You need **JetPack-compatible wheels** from NVIDIA.

```bash
# Option A: NVIDIA Official Wheels (RECOMMENDED)
# For Jetpack 6.0 with CUDA 12.2, Python 3.11

pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Verify installation
python3 -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
# Expected output:
# True
# NVIDIA Jetson Orin Nano
```

### 5.2 Alternative: L4T PyTorch (if above doesn't work)

```bash
# Download from https://nvidia.github.io/blog/updating-the-jetson-pytorch-examples/
# For Orin Nano with JetPack 6.0

wget https://nvidia-ai-iot.github.io/jetson-pytorch/wheels/torch-2.1.0-cp311-cp311-linux_aarch64.whl
pip install torch-2.1.0-cp311-cp311-linux_aarch64.whl
```

---

## 6. OPENCV-CUDA OPTIMIZATION (Optional but Recommended)

### 6.1 Compile OpenCV with CUDA

For maximum performance, compile OpenCV from source:

```bash
# Install dependencies
sudo apt install -y build-essential cmake git libgtk-3-dev pkg-config libavcodec-dev libavformat-dev libswscale-dev

# Download OpenCV
git clone https://github.com/opencv/opencv.git
cd opencv
git checkout 4.8.1

# Build with CUDA
mkdir build && cd build

cmake -D CMAKE_BUILD_TYPE=Release \
      -D CMAKE_INSTALL_PREFIX=/usr/local \
      -D CUDA_TOOLKIT_ROOT_DIR=/usr/local/cuda \
      -D WITH_CUDA=ON \
      -D WITH_CUDNN=ON \
      -D CUDA_ARCH_BIN="8.7" \
      -D CUDA_FAST_MATH=ON \
      -D WITH_CUBLAS=ON \
      -D BUILD_PYTHON_SUPPORT=ON \
      -D PYTHON_EXECUTABLE=$(which python3) \
      ..

make -j4  # Orin Nano has 8 cores, but 4 is safer to avoid RAM issues
sudo make install
```

### 6.2 Or Use Pre-built CUDA-enabled OpenCV

```bash
# Some users provide pre-built wheels
pip install opencv-contrib-python-headless
```

---

## 7. REALSENSE SDK INSTALLATION

### 7.1 Add RealSense Repository

```bash
# Install RealSense SDK 2.54.1 (latest for Jetson)
sudo apt install -y librealsense2-utils librealsense2-dev

# Alternative: Build from source (if repo version is old)
git clone https://github.com/IntelRealSense/librealsense.git
cd librealsense
mkdir build && cd build
cmake -D CMAKE_BUILD_TYPE=Release -D RSUSB_BACKEND=ON ..
make -j4
sudo make install
```

### 7.2 Python Bindings

```bash
pip install pyrealsense2

# Test
python3 -c "import pyrealsense2; print('RealSense OK')"
```

---

## 8. MODIFYING YOUR CODE FOR JETSON

### 8.1 Update `gpu_processing.py`

Replace `torch.cuda.get_device_name(0)` check to handle Jetson:

```python
# BEFORE (Windows-only):
print(f"[GPU Processing] CUDA Device: {torch.cuda.get_device_name(0)}")

# AFTER (Jetson + Windows compatible):
try:
    device_name = torch.cuda.get_device_name(0)
except Exception:
    device_name = "Unknown GPU"
print(f"[GPU Processing] CUDA Device: {device_name}")
```

### 8.2 Update `gui.py` - Remove Windows-Specific Winsound

```python
# BEFORE:
try:
    import winsound as _winsound  # type: ignore
except Exception:
    _winsound = None

# AFTER:
import platform
try:
    if platform.system() == "Windows":
        import winsound as _winsound  # type: ignore
    else:
        _winsound = None
except Exception:
    _winsound = None
```

### 8.3 Update `gui.py` - Path Handling

```python
# Use pathlib for cross-platform paths (ALREADY DONE, good!)
from pathlib import Path

base_dir = Path(__file__).resolve().parent
sign_icon_dir = base_dir / "gui_assets" / "signstocluster"
```

### 8.4 Update Serial Port Names

```python
# BEFORE (Windows):
self._elm_port = "COM12"

# AFTER (Auto-detect):
import platform

if platform.system() == "Linux":
    self._elm_port = "/dev/ttyUSB0"  # Linux (Jetson)
elif platform.system() == "Windows":
    self._elm_port = "COM12"  # Windows
else:
    self._elm_port = "/dev/cu.usbserial"  # macOS
```

### 8.5 Create Platform Detection Helper

Create file `config/platform.py`:

```python
# config/platform.py
import platform
import os

IS_JETSON = os.path.exists("/etc/nv_tegra_release")
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MAC = platform.system() == "Darwin"

SYSTEM_NAME = "Jetson Orin Nano" if IS_JETSON else platform.system()

def get_serial_port():
    if IS_JETSON or IS_LINUX:
        return "/dev/ttyUSB0"
    elif IS_WINDOWS:
        return "COM12"
    else:
        return "/dev/cu.usbserial"

def get_audio_backend():
    if IS_JETSON:
        return None  # Jetson uses different audio
    elif IS_WINDOWS:
        return "winsound"
    else:
        return None
```

Then use in `gui.py`:

```python
from config.platform import IS_JETSON, get_serial_port, get_audio_backend

# ...in gui.py constructor:
self._elm_port = get_serial_port()
```

---

## 9. PYTORCH MODEL OPTIMIZATION FOR JETSON

### 9.1 Quantize Models (Reduce Size)

For faster inference on Jetson Nano, quantize your MLP models:

```python
# File: quantize_models.py

import torch
import torch.quantization as quantization

def quantize_model(model_path, output_path):
    """Convert FP32 model to INT8 for Jetson."""
    
    model = torch.load(model_path)
    model.eval()
    
    # Prepare model for static quantization
    model_prepared = quantization.prepare(model)
    model_quantized = quantization.convert(model_prepared)
    
    torch.save(model_quantized, output_path)
    print(f"Quantized model saved to {output_path}")

# Usage:
# quantize_model("dataset/best.pt", "dataset/best_int8.pt")
```

### 9.2 Update Model Loading in `qt_read_sign.py`

```python
# Use quantized model on Jetson
import platform

if "jetson" in platform.platform().lower() or os.path.exists("/etc/nv_tegra_release"):
    MODEL_PATH = "dataset/best_int8.pt"  # Quantized
else:
    MODEL_PATH = "dataset/best.pt"  # Full precision
```

---

## 10. PERFORMANCE TUNING FOR JETSON NANO

### 10.1 Enable Max Performance Mode

```bash
# SSH to Jetson
ssh ubuntu@jetson.local

# Set to MAX performance (not power-saving)
sudo jetson_clocks

# Make it permanent
sudo systemctl enable jetson_clocks

# Check frequencies
cat /sys/devices/virtual/thermal/cooling_device*/cur_state
```

### 10.2 Increase VRAM Allocation

```bash
# Edit /boot/extlinux/extlinux.conf
sudo nano /boot/extlinux/extlinux.conf

# Add to APPEND line:
# cma=256M   (increase from default 128M)

# Reboot
sudo reboot
```

### 10.3 Monitor Performance

```bash
# Real-time stats
jtop  # Install: pip install jetson-stats

# Or use standard tools
watch nvidia-smi
ps aux | grep python
top -bn1 | head -20
```

---

## 11. TRANSFERRING PROJECT TO JETSON

### 11.1 Copy Files via SCP

```bash
# On your Windows PC
scp -r "C:\Users\Minko\Desktop\DP\VisionPilot-XR Linux" ubuntu@jetson.local:~/visionpilot

# Or use WinSCP (GUI)
```

### 11.2 Create Required Directories

```bash
# On Jetson
cd ~/visionpilot
mkdir -p log_files detections data_analysis CAN_logs MLP_report gui_assets
```

---

## 12. TESTING ON JETSON

### 12.1 Test Individual Modules

```bash
# On Jetson, activate venv
source ~/visionpilot/bin/activate
cd ~/visionpilot

# Test imports
python3 -c "import torch; print('PyTorch OK'); import cv2; print('OpenCV OK')"

# Test GPU
python3 -c "
import torch
print(f'CUDA Available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'Device: {torch.cuda.get_device_name(0)}')
    print(f'GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB')
"

# Test RealSense
python3 -c "
import pyrealsense2 as rs
ctx = rs.context()
devices = ctx.query_devices()
print(f'RealSense devices found: {devices.size()}')
"

# Test ELM327
python3 -c "
from elm327_can_speed import ELM327SpeedReader
print('ELM327 module OK')
"
```

### 12.2 Run GUI on Jetson

```bash
# Via SSH with X11 forwarding (slow, but works for testing)
ssh -X ubuntu@jetson.local
cd ~/visionpilot
python3 gui.py

# OR run headless on Jetson, display on PC (better)
# Export DISPLAY
export DISPLAY=<your_windows_ip>:0  # requires X server on Windows
```

### 12.3 Alternative: Use VNC

```bash
# On Jetson
sudo apt install -y vino

# Configure VNC
gsettings set org.gnome.desktop.remote-access enabled true

# On Windows, use VNC viewer (RealVNC, TightVNC, etc.)
# Connect to: jetson.local:5900
```

---

## 13. COMMON ISSUES & FIXES

### Issue 1: "ModuleNotFoundError: No module named 'torch'"

**Solution:**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Issue 2: "No CUDA-capable device detected"

**Solution:**
```bash
# Check if CUDA is properly installed
nvcc --version
nvidia-smi

# If nvidia-smi fails, CUDA drivers are missing
sudo apt install -y nvidia-cuda-toolkit
sudo reboot
```

### Issue 3: GUI window doesn't appear

**Solution:**
```bash
# Ensure DISPLAY is set
echo $DISPLAY  # Should show :0 or :1

# If empty, set it
export DISPLAY=:0

# Or use Xvfb if no display
sudo apt install -y xvfb
Xvfb :99 -screen 0 1024x768x24 &
export DISPLAY=:99
```

### Issue 4: RealSense camera not detected

**Solution:**
```bash
# Check USB connection
lsusb | grep RealSense

# List video devices
ls -la /dev/video*

# Rebuild RealSense with proper permissions
sudo usermod -a -G video $USER
sudo reboot
```

### Issue 5: Out of memory errors

**Solution:**
```bash
# Reduce image resolution
# In gui.py, change resolution to 1280x720 or 848x480

# Reduce batch processing
# In image_processing.py, lower processing throughput

# Monitor memory
free -h
watch -n 1 'free -h'
```

### Issue 6: Slow inference on Jetson Nano

**Possible fixes:**
1. Use quantized models (`best_int8.pt`)
2. Reduce input image resolution
3. Enable TensorRT (faster than PyTorch)
4. Use TorchScript compilation

---

## 14. OPTIMIZATION CHECKLIST

- [ ] JetPack 6.0+ installed and CUDA verified
- [ ] Python 3.11 venv created
- [ ] PyTorch ARM64 wheels installed
- [ ] OpenCV compiled with CUDA support (optional but recommended)
- [ ] RealSense SDK installed with Python bindings
- [ ] Code updated for cross-platform compatibility
- [ ] Serial port configured for `/dev/ttyUSB0`
- [ ] GUI tested with X11 or VNC
- [ ] Models quantized for Jetson Nano
- [ ] Performance monitoring tools installed (`jtop`, `nvidia-smi`)
- [ ] Heat sink and proper cooling setup
- [ ] Power supply 25W+ confirmed

---

## 15. DEPLOYMENT SCRIPT

Create `run_visionpilot.sh` on Jetson:

```bash
#!/bin/bash

# Activate virtual environment
source ~/visionpilot/bin/activate

# Enable max performance
sudo jetson_clocks

# Optional: Set DISPLAY if needed
export DISPLAY=:0

# Run GUI
cd ~/visionpilot
python3 gui.py

# Or run in background
# nohup python3 gui.py > /tmp/visionpilot.log 2>&1 &
```

Make it executable:
```bash
chmod +x run_visionpilot.sh
./run_visionpilot.sh
```

---

## 16. REMOTE ACCESS FROM WINDOWS PC

### 16.1 SSH Access

```powershell
# Windows PowerShell
ssh ubuntu@jetson.local
# Or: ssh -i "C:\path\to\key.pem" ubuntu@jetson.local
```

### 16.2 WinSCP for File Transfer

Download: https://winscp.net/

```
Hostname: jetson.local
Port: 22
Username: ubuntu
Password: <password>
```

### 16.3 VS Code Remote (Best for Development)

1. Install "Remote - SSH" extension
2. Command Palette → "Remote-SSH: Add New SSH Host"
3. Enter: `ssh ubuntu@jetson.local`
4. Open folder: `/home/ubuntu/visionpilot`

---

## FINAL NOTES

Your code is **already well-structured** for Jetson:
- ✅ Uses `pathlib` for cross-platform paths
- ✅ Graceful fallback for optional dependencies
- ✅ Modular architecture
- ✅ GPU/CPU hybrid approach

The main changes needed are:
1. Serial port configuration (`COM12` → `/dev/ttyUSB0`)
2. Remove Windows-specific audio (`winsound`)
3. Use ARM64 PyTorch wheels
4. Optional: Compile OpenCV with CUDA

**Good luck! 🚀**

