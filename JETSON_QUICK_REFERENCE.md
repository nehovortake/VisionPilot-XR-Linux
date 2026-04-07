# VisionPilot XR - Jetson Orin Nano - QUICK REFERENCE

## 📌 TRI HLAVNÉ ZMENY V KÓDE

### 1. gpu_processing.py (1 zmena)
```python
# BEFORE:
print(f"[GPU Processing] CUDA Device: {torch.cuda.get_device_name(0)}")

# AFTER:
try:
    device_name = torch.cuda.get_device_name(0)
except Exception:
    device_name = "Unknown GPU"
print(f"[GPU Processing] CUDA Device: {device_name}")
```

### 2. gui.py (2 zmeny)

**ZMENA 1** - Platform Detection (na začiatku súboru):
```python
import platform
import os

# Add after imports
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_JETSON = IS_LINUX and os.path.exists("/etc/nv_tegra_release")

# Change winsound import
try:
    if IS_WINDOWS:
        import winsound as _winsound
    else:
        _winsound = None
except Exception:
    _winsound = None
```

**ZMENA 2** - Serial Port Auto-Detection (v BackgroundWindow.__init__):
```python
# BEFORE:
self._elm_port = "COM12"

# AFTER:
if IS_JETSON or IS_LINUX:
    self._elm_port = "/dev/ttyUSB0"
elif IS_WINDOWS:
    self._elm_port = "COM12"
else:
    self._elm_port = "/dev/cu.usbserial"
```

### 3. Nový súbor: config/platform_config.py
- Centralizovaná konfigurácia pre všetky platformy
- Automatické detekcie Jetson
- Helper funkcie pre cesty a nastavenia

---

## 🎯 INSTALLATION CHEAT SHEET

```bash
# 1. SSH to Jetson
ssh ubuntu@jetson.local

# 2. Update system
sudo apt update && sudo apt upgrade -y

# 3. Create venv
python3.11 -m venv ~/visionpilot
source ~/visionpilot/bin/activate

# 4. Install PyTorch ARM64 (CRITICAL!)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 5. Install other dependencies
pip install -r requirements_jetson.txt

# 6. Test installation
python3 jetson_test.py

# 7. Run GUI
export DISPLAY=:0
python3 gui.py

# Alternative: Use VNC (recommended)
# On Windows: Download VNC Viewer
# Connect to: jetson.local:5900
```

---

## ✅ VERIFIKÁCIA - Čo Skontrolovať

```bash
# Is Jetson detected?
python3 -c "import os; print('Is Jetson:', os.path.exists('/etc/nv_tegra_release'))"

# Is CUDA available?
python3 -c "import torch; print('CUDA:', torch.cuda.is_available())"

# Which serial port?
python3 -c "
from config.platform_config import IS_JETSON, get_serial_port
print(f'Jetson: {IS_JETSON}')
print(f'Serial Port: {get_serial_port()}')
"

# Full test
python3 jetson_test.py
```

---

## 📁 SÚBORY V PROJEKTU

### Upravené (kompatibilní s Jetson) ✅
- `gui.py` - Platform detection + serial port auto-detect
- `gpu_processing.py` - CUDA device name handling

### Nové (pre Jetson) ✅
- `config/platform_config.py` - Centralizovaná konfigurácia
- `jetson_test.py` - Komplexný test všetkých závislostí
- `run_visionpilot.sh` - Launcher script
- `requirements_jetson.txt` - Pip requirements

### Dokumentácia ✅
- `JETSON_DEPLOYMENT_SUMMARY.md` - Přehled (tento súbor)
- `JETSON_INSTALLATION_GUIDE_SK.md` - Detailný slovenský návod
- `JETSON_SETUP_GUIDE.md` - Detailný anglický návod
- `JETSON_PATCHES.md` - Opis všetkých zmien

---

## 🚨 KRITICKÉ KRÔKY

1. **PyTorch ARM64 wheels** (MUST!)
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```
   - Bez toho GUI sa nikdy neztartuje na Jetson
   - Normálny `pip install torch` pre ARM64 NEFUNGUJE

2. **Serial Port Configuration**
   - Linux/Jetson: `/dev/ttyUSB0`
   - Windows: `COM12`
   - Automaticky detekovaný v `gui.py`

3. **Display Configuration** (pre GUI)
   - SSH s X11: `ssh -X ubuntu@jetson.local`
   - VNC: Stiahnite si VNC Viewer → `jetson.local:5900`
   - Headless: Možné, ale bez grafiky

---

## 🔍 DIAGNOSTIKA

### Test 1: Check Python
```bash
source ~/visionpilot/bin/activate
python3 --version
```

### Test 2: Check CUDA
```bash
python3 -c "
import torch
print('CUDA Available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('Device:', torch.cuda.get_device_name(0))
    print('CUDA Version:', torch.version.cuda)
"
```

### Test 3: Check RealSense
```bash
lsusb | grep RealSense
python3 -c "import pyrealsense2 as rs; print('RealSense OK')"
```

### Test 4: Check Serial Port
```bash
ls -la /dev/ttyUSB*
python3 -c "
import serial.tools.list_ports
for port in serial.tools.list_ports.comports():
    print(f'{port.device}: {port.description}')
"
```

### Test 5: Run Full Test Suite
```bash
python3 jetson_test.py
```

---

## 🎮 SPUSTENIE

### Option 1: Direct Run
```bash
source ~/visionpilot/bin/activate
export DISPLAY=:0
python3 gui.py
```

### Option 2: Using Launcher Script
```bash
chmod +x run_visionpilot.sh
./run_visionpilot.sh
```

### Option 3: Background Service
```bash
sudo systemctl start visionpilot
sudo systemctl status visionpilot
sudo journalctl -u visionpilot.service -f
```

---

## 📊 PERFORMANCE TUNING

```bash
# Enable max performance
sudo jetson_clocks

# Monitor in real-time
jtop

# Check CPU/Memory
top
free -h
ps aux | grep python3

# Check GPU
nvidia-smi
nvidia-smi dmon
```

---

## 🐛 COMMON ISSUES

| Problem | Solution |
|---------|----------|
| `No module 'torch'` | `pip install torch --index-url https://download.pytorch.org/whl/cu121` |
| CUDA not available | Run `nvcc --version` and `nvidia-smi` |
| GUI window missing | Set `export DISPLAY=:0` or use VNC |
| Camera not detected | Check `lsusb`, run `sudo usermod -a -G video $USER` |
| Serial port not found | Check `/dev/ttyUSB*`, connect OBD-II adapter |
| Out of memory | Reduce resolution to 1280x720, FPS to 15 |

---

## 🔗 LINKS

- Jetson Orin Nano Docs: https://docs.nvidia.com/jetson/orin-nano/
- PyTorch Download: https://pytorch.org/
- RealSense SDK: https://github.com/IntelRealSense/librealsense
- VNC Viewer: https://www.realvnc.com/
- Jetson Stats: https://github.com/rbonghi/jetson_stats

---

## 📝 NOTES

- Your code is **well-structured** for cross-platform use
- The changes are **minimal** and **backward-compatible**
- Windows deployment is **NOT AFFECTED** ✅
- Jetson deployment now **FULLY SUPPORTED** ✅

**DEPLOYMENT READY! 🚀**

