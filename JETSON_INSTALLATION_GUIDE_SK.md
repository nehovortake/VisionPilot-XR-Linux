# VisionPilot XR - NVIDIA Jetson Orin Nano - Rýchly Sprievodca

## ZMENY APLIKOVANÉ VÁŠ KÓDE ✅

Nasledujúce úpravy už boli aplikované, aby váš kód fungoval na Jetson Orin Nano:

### 1. **gpu_processing.py** - Oprava načítania názvu CUDA zariadenia
- **Zmena**: Pridaný try-except blok pre `torch.cuda.get_device_name(0)`
- **Dôvod**: Jetson má odlišné rozhranie CUDA ako klasické GPU
- **Efekt**: GUI sa spustí bez chyby na Jetson

### 2. **gui.py** - Detekcia platformy + serial port
- **Zmena 1**: Pridané rozpoznanie platformy (Windows/Linux/Jetson)
- **Zmena 2**: Podmienené importovanie `winsound` len na Windows
- **Zmena 3**: Auto-detekcia sériového portu:
  - Windows: `COM12`
  - Linux/Jetson: `/dev/ttyUSB0`
  - macOS: `/dev/cu.usbserial`

### 3. **Nový modul** - `config/platform_config.py`
- Centralizovaná konfigurácia pre rôzne platformy
- Automatické rozpoznanie Jetson zariadenia
- Optimálne nastavenia rozlíšenia/FPS pre Jetson Nano

---

## POŽIADAVKY PRE JETSON ORIN NANO

### Hardware
- ✅ NVIDIA Jetson Orin Nano 8GB (ideálne)
- ✅ Heatsink + chladzenie
- ✅ 25W+ napájanie
- ✅ RealSense D435i kamera (USB)
- ✅ OBD-II adapter ELM327 (USB)
- ✅ microSD karta 64GB+ (pre JetPack OS)
- ✅ Ethernet alebo WiFi pripojenie

### Software (JetPack 6.0+)
- ✅ Ubuntu 22.04 LTS
- ✅ CUDA 12.2
- ✅ cuDNN 8.9+
- ✅ TensorRT (pre optimizáciu modelov)

---

## INŠTALÁCIA NA JETSON - KROK ZA KROKOM

### KROK 1: Príprava Jetson (počítač bez Jetson)

```bash
# Na PC s Windows
# 1. Stiahnite si SDK Manager: https://developer.nvidia.com/sdk-manager
# 2. Pripojte Jetson v Recovery Mode:
#    - Podržte POWER + RESET, potom pusťte iba POWER
# 3. Flashnite JetPack 6.0 s Ubuntu 22.04 + CUDA 12.2
```

### KROK 2: Prvé spustenie Jetson

```bash
# Po spustení Jetson (SSH alebo cez HDMI):
ssh ubuntu@jetson.local
# Heslo: ubuntu (zmeniť neskôr!)

# Aktualizácia systému
sudo apt update && sudo apt upgrade -y
sudo reboot
```

### KROK 3: Vytvorenie Python Virtual Environment

```bash
# SSH do Jetson
ssh ubuntu@jetson.local

# Inštalácia dev nástrojov
sudo apt install -y python3.11-dev python3.11-venv

# Vytvorenie venv
python3.11 -m venv ~/visionpilot
source ~/visionpilot/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### KROK 4: Inštalácia PyTorch pre ARM64 (KRITICKÉ!)

```bash
# Aktivujte venv
source ~/visionpilot/bin/activate

# Oficiálne NVIDIA PyTorch wheels pre Jetson + CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Verifikácia
python3 -c "import torch; print('CUDA:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0))"
# Očakávaný výstup:
# CUDA: True
# Device: NVIDIA Jetson Orin Nano
```

### KROK 5: Inštalácia zvyšných zavislostí

```bash
# Stále v venv:
pip install opencv-python numpy scipy
pip install PyQt5
pip install pyserial psutil
pip install pyrealsense2

# Verifikácia všetkých importov
python3 -c "
import torch; print('✓ PyTorch')
import cv2; print('✓ OpenCV')
import pyrealsense2; print('✓ RealSense')
import serial; print('✓ PySerial')
import numpy; print('✓ NumPy')
import psutil; print('✓ PSUtil')
from PyQt5.QtWidgets import QApplication; print('✓ PyQt5')
"
```

### KROK 6: Kopírování projektu do Jetson

```bash
# Na vašom Windows PC (PowerShell):
scp -r "C:\Users\Minko\Desktop\DP\VisionPilot-XR Linux\*" ubuntu@jetson.local:~/visionpilot/

# Alebo použite WinSCP (GUI):
# Hostname: jetson.local, Port: 22, Username: ubuntu
```

### KROK 7: Vrstvenie požadovaných priečinkov

```bash
# SSH na Jetson
ssh ubuntu@jetson.local
cd ~/visionpilot

# Vytvorenie priečinkov
mkdir -p log_files detections data_analysis CAN_logs MLP_report
chmod -R 755 log_files detections data_analysis CAN_logs MLP_report
```

### KROK 8: Test jednotlivých modulov

```bash
# Aktivujte venv
source ~/visionpilot/bin/activate
cd ~/visionpilot

# Test image_processing
python3 -c "
from gpu_processing import CUDA_AVAILABLE
print(f'GPU Acceleration: {CUDA_AVAILABLE}')
"

# Test ELM327
python3 -c "from elm327_can_speed import ELM327SpeedReader; print('✓ ELM327 OK')"

# Test RealSense
python3 -c "
import pyrealsense2 as rs
ctx = rs.context()
devices = ctx.query_devices()
print(f'RealSense devices: {devices.size()}')
"

# Test GUI (headless - bez grafiky)
python3 -c "
from PyQt5.QtWidgets import QApplication
from config.platform_config import IS_JETSON, SYSTEM_NAME
print(f'System: {SYSTEM_NAME}')
print(f'Is Jetson: {IS_JETSON}')
print('✓ GUI initialization OK')
"
```

---

## SPUSTENIE GUI NA JETSON

### Možnosť 1: SSH s X11 Forwarding (pomalé, ale jednoduché)

```bash
# Na Windows PC (vyžaduje X server):
# Stiahnite si VcXsrv alebo Xming

# SSH s forwarding
ssh -X ubuntu@jetson.local
export DISPLAY=:0
cd ~/visionpilot
python3 gui.py
```

### Možnosť 2: VNC (Odporúčané - najrýchlejšie)

```bash
# Na Jetson - inštalácia VNC servera
sudo apt install -y vino tigervnc-standalone-server

# Nastavenie VNC
gsettings set org.gnome.desktop.remote-access enabled true

# Na Windows PC - inštalácia VNC Viewer:
# https://www.realvnc.com/en/connect/download/viewer/
# Pripojenie: jetson.local:5900

# Spustenie aplikácie v Jetson terminále
source ~/visionpilot/bin/activate
cd ~/visionpilot
python3 gui.py
```

### Možnosť 3: Systemd Service (pre automatické spustenie)

```bash
# Na Jetson - vytvorenie služby
sudo nano /etc/systemd/system/visionpilot.service
```

Vložte:
```ini
[Unit]
Description=VisionPilot XR
After=network.target
Wants=display-manager.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/visionpilot
Environment="PATH=/home/ubuntu/visionpilot/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="DISPLAY=:0"
ExecStart=/home/ubuntu/visionpilot/bin/python3 gui.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=graphical.target
```

Potom:
```bash
sudo systemctl daemon-reload
sudo systemctl enable visionpilot.service
sudo systemctl start visionpilot.service
# Kontrola stavu
sudo systemctl status visionpilot.service
```

---

## OPTIMIZÁCIA VÝKONU PRE JETSON NANO

### Maximálny výkon

```bash
# Na Jetson - povolenie maximálneho výkonu
sudo jetson_clocks

# Trvalá aktivácia
sudo systemctl enable jetson_clocks
sudo systemctl start jetson_clocks

# Kontrola frekvencií
cat /sys/devices/virtual/thermal/cooling_device*/cur_state
```

### Monitoring výkonu

```bash
# Inštalácia jtop
pip install jetson-stats

# Spustenie
jtop  # Interaktívny monitor (ESC na exit)

# Alebo klasický nvidia-smi
watch nvidia-smi

# Kontrola pamäte
free -h
watch -n 1 'free -h'
```

### Optimizácia rozlíšenia kamery

V `gui.py` alebo `config/platform_config.py`:
```python
# Pre Jetson Nano odporúčané:
OPTIMAL_RESOLUTION = (1280, 720)  # Namiesto (1920, 1080)
OPTIMAL_FPS = 15  # Namiesto 30
```

---

## POKYNY PRE INŠTALÁCIU ELM327 DRIVERA

### Na Jetson Linux

```bash
# Pripojte USB adapter
# Kontrola pripojenia
lsusb | grep "USB"

# Inštalácia udev pravidiel
sudo apt install -y udev

# Vytvorenie pravidla pre ELM327
sudo nano /etc/udev/rules.d/50-elm327.rules
```

Vložte:
```
# ELM327 OBD-II Adapter
SUBSYSTEM=="tty", ATTRS{idVendor}=="067b", ATTRS{idProduct}=="2303", SYMLINK+="elm327", MODE="0666"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="elm327", MODE="0666"
```

Potom:
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger

# Kontrola pripojenia
ls -la /dev/ttyUSB*
# Mali by ste vidieť /dev/ttyUSB0
```

---

## BEŽNÉ CHYBY A RIEŠENIA

### ❌ Chyba: "ModuleNotFoundError: No module named 'torch'"

```bash
# Riešenie:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### ❌ Chyba: "CUDA not available"

```bash
# Kontrola CUDA inštalácie
nvcc --version
nvidia-smi

# Ak nvidia-smi zlyhá:
sudo apt install -y nvidia-cuda-toolkit
sudo reboot
```

### ❌ Chyba: "GUI window doesn't appear"

```bash
# Nastavenie DISPLAY
echo $DISPLAY  # Mali by ste vidieť :0 alebo :1

# Ak prázdne, nastavte
export DISPLAY=:0

# Alebo použite VNC (lepšie)
```

### ❌ Chyba: "RealSense camera not detected"

```bash
# Kontrola USB pripojenia
lsusb | grep RealSense

# Reset USB portu
sudo uhd_power_off.py  # ak existuje

# Alebo obnova ovládačov
sudo apt reinstall -y librealsense2

# Kontrola oprávnení
sudo usermod -a -G video $USER
sudo reboot
```

### ❌ Chyba: "Out of memory"

```bash
# Zmenšenie rozlíšenia v gui.py
# Zmena z (1920, 1080) na (1280, 720)

# Zníženie FPS
# Zmena z 30 na 15 FPS

# Vypnutie menej dôležitých funkcií
# Vypnite RED, CANNY spracovanie ak potrebujete iba detekciu
```

---

## NASTAVENIA PRE OPTIMALIZÁCIU MODELOV (Voliteľné)

### Quantizácia modelov (čiže zmenšenie veľkosti)

Na Jetson je vhodné používať INT8 quantizované modely pre rýchlejšiu inferenciu:

```bash
# Na Jetson
source ~/visionpilot/bin/activate

# Stiahnite si skript
# (Vytvorte súbor quantize_models.py)

python3 quantize_models.py

# Výsledok: dataset/best_int8.pt (menší, rýchlejší)
```

---

## VZDIALENÝ PRÍSTUP ZO WINDOWS PC

### SSH Connection

```powershell
# PowerShell
ssh ubuntu@jetson.local
# Heslo: ubuntu

# S private key
ssh -i "C:\Users\Minko\.ssh\id_rsa" ubuntu@jetson.local
```

### WinSCP (súborový manažér)

1. Stiahnite: https://winscp.net/
2. Připojte:
   - Hostname: `jetson.local`
   - Port: `22`
   - Username: `ubuntu`
   - Password: `ubuntu`

### Visual Studio Code Remote

1. Inštalujte extension "Remote - SSH"
2. Cmdpalette → "Remote-SSH: Add New SSH Host"
3. Zadajte: `ssh ubuntu@jetson.local`
4. Otvorte priečinok: `/home/ubuntu/visionpilot`

---

## FINÁLNY CHECKLIST ✅

Pred spustením v produkcii:

- [ ] JetPack 6.0+ s CUDA 12.2 nainštalovaný
- [ ] Python 3.11 venv vytvorený a aktivovaný
- [ ] PyTorch ARM64 wheels nainštalované a testované
- [ ] RealSense SDK nainštalovaný a kamera testovaná
- [ ] Projekt skopírovaný do `/home/ubuntu/visionpilot`
- [ ] Všetky importy testované (viď KROK 5)
- [ ] Serial port `/dev/ttyUSB0` pripravený
- [ ] GUI testovaný cez VNC alebo SSH+X11
- [ ] Jetson Clocks aktivovaný pre maximálny výkon
- [ ] Monitoring nástrojov (`jtop`) nainštalovaný
- [ ] Heatsink pripevnený a chladenie funčné
- [ ] Záloha modelov `dataset/best.pt` vytvorená

---

## ĎALŠIE ZDROJE

- **JetPack Dokumentácia**: https://docs.nvidia.com/jetson/
- **PyTorch na Jetson**: https://nvidia.github.io/blog/updating-the-jetson-pytorch-examples/
- **RealSense Jetson**: https://github.com/IntelRealSense/librealsense/blob/master/doc/installation_jetson.md
- **Jetson Stats**: https://github.com/rbonghi/jetson_stats

---

**Vašá aplikácia je teraz pripravená na NVIDIA Jetson Orin Nano! 🚀**

Ak máte problémy, skontrolujte terminál s výstupom chýb a použite `journalctl -u visionpilot.service -n 50` na kontrolu logov služby.

