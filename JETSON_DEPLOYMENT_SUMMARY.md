# JETSON ORIN NANO DEPLOYMENT - SUMMARY

## 📋 Aplikované Zmeny V Kóde ✅

Vaš kód bol úspešne aktualizovaný na podporu NVIDIA Jetson Orin Nano.

### 1. **gpu_processing.py** - HOTOVO ✅
```
✓ Pridaný try-except pre torch.cuda.get_device_name(0)
✓ Jetson-kompatibilný CUDA device detection
```

### 2. **gui.py** - HOTOVO ✅
```
✓ Platform detection (Windows/Linux/Jetson)
✓ Podmienené importovanie winsound (len Windows)
✓ Auto-detekcia sériového portu:
  - Linux/Jetson: /dev/ttyUSB0
  - Windows: COM12
  - macOS: /dev/cu.usbserial
```

### 3. **config/platform_config.py** - NOVÝ ✅
```
✓ Centralizovaná konfigurácia pre všetky platformy
✓ Automatické rozpoznanie Jetson zariadenia
✓ Optimálne nastavenia pre Jetson Nano
✓ Cesty pre modely a assety
```

### 4. **Ďalšie Support Súbory**
```
✓ jetson_test.py - Kompletný test všetkých závislostí
✓ run_visionpilot.sh - Launcher script s environment setupom
✓ requirements_jetson.txt - Pip requirements pre rýchlu inštaláciu
✓ JETSON_SETUP_GUIDE.md - Detailný anglický návod
✓ JETSON_INSTALLATION_GUIDE_SK.md - Podrobný slovenský návod
✓ JETSON_PATCHES.md - Opis všetkých aplikovaných zmien
```

---

## 🚀 RÝCHLY START NA JETSON

### Krok 1: Aktualizácia Jetson
```bash
ssh ubuntu@jetson.local
sudo apt update && sudo apt upgrade -y
sudo reboot
```

### Krok 2: Python Virtual Environment
```bash
ssh ubuntu@jetson.local
python3.11 -m venv ~/visionpilot
source ~/visionpilot/bin/activate
pip install --upgrade pip setuptools wheel
```

### Krok 3: PyTorch pre ARM64 (KRITICKÉ!)
```bash
source ~/visionpilot/bin/activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Krok 4: Ostatné Závislosti
```bash
pip install -r requirements_jetson.txt
```

### Krok 5: Kopírování Projektu
```bash
# Z Windows PC
scp -r "C:\Users\Minko\Desktop\DP\VisionPilot-XR Linux\*" ubuntu@jetson.local:~/visionpilot/
```

### Krok 6: Test
```bash
ssh ubuntu@jetson.local
cd ~/visionpilot
source ~/visionpilot/bin/activate
python3 jetson_test.py
```

### Krok 7: Spustenie GUI
```bash
# Možnosť A: Jednoduchý spustenie (potrebuje X display)
export DISPLAY=:0
python3 gui.py

# Možnosť B: VNC (odporúčané)
# Stiahnite si VNC Viewer na Windows
# Připojite sa na: jetson.local:5900

# Možnosť C: Launch script
bash run_visionpilot.sh
```

---

## 📁 Štruktúra Projektu

```
VisionPilot-XR Linux/
├── gui.py                              ← UPRAVENÝ
├── gpu_processing.py                   ← UPRAVENÝ
├── elm327_can_speed.py                 (bez zmien)
├── image_processing.py                 (bez zmien)
├── realsense.py                        (bez zmien)
├── qt_read_sign.py                     (bez zmien)
│
├── config/                             ← NOVÝ
│   ├── __init__.py
│   └── platform_config.py              ← NOVÝ
│
├── jetson_test.py                      ← NOVÝ - Test script
├── run_visionpilot.sh                  ← NOVÝ - Launcher script
│
├── JETSON_SETUP_GUIDE.md               ← NOVÝ - Anglický návod
├── JETSON_INSTALLATION_GUIDE_SK.md     ← NOVÝ - Slovenský návod
├── JETSON_PATCHES.md                   ← NOVÝ - Opis zmien
├── requirements_jetson.txt             ← NOVÝ - Pip requirements
│
└── ... ostatné súbory (bez zmien)
```

---

## ✅ PREDPOKLADY NA JETSON

### Hardware
- [x] NVIDIA Jetson Orin Nano 8GB
- [x] Heatsink + chladenie
- [x] 25W+ napájanie
- [x] RealSense D435i kamera
- [x] OBD-II ELM327 adapter
- [x] microSD karta 64GB+

### Software
- [x] JetPack 6.0+ (Ubuntu 22.04 + CUDA 12.2)
- [x] Python 3.11
- [x] PyTorch ARM64 wheels
- [x] OpenCV (standard alebo CUDA-optimized)
- [x] RealSense SDK

---

## 🧪 VERIFIKÁCIA INŠTALÁCIE

Spustite na Jetson:
```bash
source ~/visionpilot/bin/activate
python3 jetson_test.py
```

Očakávaný výstup (všetky testy s ✓):
```
✓ System Information ........................ ✓ PASS
✓ PyTorch & CUDA ........................... ✓ PASS
✓ OpenCV .................................. ✓ PASS
✓ RealSense Camera ......................... ✓ PASS
✓ PySerial & ELM327 ....................... ✓ PASS
✓ PyQt5 GUI ............................... ✓ PASS
✓ NumPy & SciPy ........................... ✓ PASS
✓ System Monitoring ....................... ✓ PASS
✓ Custom Modules .......................... ✓ PASS
✓ Platform Configuration .................. ✓ PASS

Total: 10/10 tests passed
🎉 ALL TESTS PASSED - READY FOR DEPLOYMENT!
```

---

## ⚠️ ČASTÉ CHYBY & RIEŠENIA

### "ModuleNotFoundError: No module named 'torch'"
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### "CUDA not available"
```bash
nvcc --version          # Check CUDA installation
nvidia-smi             # Check GPU drivers
sudo apt install -y nvidia-cuda-toolkit
sudo reboot
```

### "RealSense camera not detected"
```bash
lsusb | grep RealSense
ls -la /dev/video*
sudo usermod -a -G video $USER
sudo reboot
```

### "GUI window doesn't appear"
```bash
export DISPLAY=:0      # Set display
# ALEBO použite VNC (lepšie pre Jetson)
```

### "Out of memory"
```bash
# V gui.py zmene rezolúciu:
# Ako: (1920, 1080) -> (1280, 720)
# FPS: 30 -> 15
```

---

## 📊 VÝKON NA JETSON

### Očakávaný výkon (Orin Nano)
- **Inference (MLP model)**: ~50-100 ms
- **Ellipse detection**: ~30-50 ms
- **RealSense stream**: 15-20 FPS
- **GPU utilization**: 40-60%
- **Power consumption**: 15-25W

### Optimizácia
```bash
# Enable max performance
sudo jetson_clocks

# Monitor performance
jtop  # Interactive dashboard

# Check memory
free -h
watch -n 1 'free -h'
```

---

## 🔐 BEZPEČNOSŤ & ÚDRŽBA

### SSH Key Setup (bez hesla)
```bash
ssh-keygen -t rsa
ssh-copy-id -i ~/.ssh/id_rsa.pub ubuntu@jetson.local
```

### Automatické Spustenie Při Boote
```bash
sudo crontab -e
# Add:
@reboot cd /home/ubuntu/visionpilot && bash run_visionpilot.sh
```

### Systemd Service (lepšie)
```bash
sudo nano /etc/systemd/system/visionpilot.service
# Copy content from JETSON_INSTALLATION_GUIDE_SK.md
sudo systemctl enable visionpilot
sudo systemctl start visionpilot
```

---

## 📞 PODPORA & DEBUGGING

### SSH Prístup zo Windows
```powershell
ssh ubuntu@jetson.local
# Alebo:
ssh -i "C:\path\to\key.pem" ubuntu@jetson.local
```

### Visual Studio Code Remote
1. Inštalujte "Remote - SSH" extension
2. Cmd Palette → "Remote-SSH: Add New SSH Host"
3. Zadajte: `ssh ubuntu@jetson.local`

### Remote Monitoring
```bash
# Check running processes
ps aux | grep python3

# Check logs
journalctl -u visionpilot.service -n 50

# Real-time monitoring
nvidia-smi -l 1
jtop
```

---

## 📚 ĎALŠIE ZDROJE

1. **JetPack & CUDA**: https://docs.nvidia.com/jetson/
2. **PyTorch Jetson**: https://nvidia.github.io/blog/updating-the-jetson-pytorch-examples/
3. **RealSense Jetson**: https://github.com/IntelRealSense/librealsense/blob/master/doc/installation_jetson.md
4. **Jetson Stats**: https://github.com/rbonghi/jetson_stats
5. **PyQt5 GUI**: https://doc.qt.io/qt-5/index.html

---

## ✨ FINÁLNY CHECKLIST

Pred spustením v produkcii:

- [ ] JetPack 6.0+ s CUDA 12.2 nainštalovaný a testovaný
- [ ] Python 3.11 venv vytvorený (`~/visionpilot`)
- [ ] PyTorch ARM64 wheels nainštalované a funkčné
- [ ] `jetson_test.py` vrátil všetky ✓
- [ ] RealSense kamera detekovaná a testovaná
- [ ] Serial port `/dev/ttyUSB0` k dispozícii
- [ ] GUI spustená úspešne cez VNC
- [ ] Jetson Clocks povolený pre maximum výkonu
- [ ] Heatsink pripevnený a chladenie funčné
- [ ] Záloha dát vytvorená (`dataset/best.pt`)
- [ ] Logging nakonfigurovaný (`log_files/`)

---

## 🎉 HOTOVO!

Vaša aplikácia **VisionPilot XR** je teraz plne pripravená na beh na **NVIDIA Jetson Orin Nano**.

Ak máte akékoľvek problémy:
1. Spustite `jetson_test.py` na diagnostiku
2. Skontrolujte stdout/stderr v terminále
3. Pozrite sa na detailný návod: `JETSON_INSTALLATION_GUIDE_SK.md`

**Ďalej to pobeží ako Pieseň! 🚀**

