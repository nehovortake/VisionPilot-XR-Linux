# 📑 VisionPilot XR - Jetson Orin Nano - DOKUMENTAČNÝ INDEX

## 🎯 KDE ZAČAŤ?

Vyber si jeden z týchto dokumentov na základe toho, čo potrebuješ:

---

## 📖 DOKUMENTÁCIA - PODĽA POTREBY

### 🚀 **Chceš RÝCHLO ZAČAŤ?**
👉 **[JETSON_QUICK_REFERENCE.md](JETSON_QUICK_REFERENCE.md)**
- ⏱️ Čas: 5 minút na čítanie
- 📝 Obsah: Cheat sheet + kritické kroky
- ✅ Vhodný pre: Skúsených vývojárov

---

### 📚 **Chceš DETAILNÝ NÁVOD (SK)?**
👉 **[JETSON_INSTALLATION_GUIDE_SK.md](JETSON_INSTALLATION_GUIDE_SK.md)**
- ⏱️ Čas: 30 minút na čítanie
- 📝 Obsah: Krok-za-krokom inštalácia
- ✅ Vhodný pre: Všetci vývojári
- 🇸🇰 Jazyk: **Slovenčina**

---

### 📚 **Chceš DETAILNÝ NÁVOD (EN)?**
👉 **[JETSON_SETUP_GUIDE.md](JETSON_SETUP_GUIDE.md)**
- ⏱️ Čas: 30 minút na čítanie
- 📝 Obsah: Kompletný setup s vysvetleniami
- ✅ Vhodný pre: Všetci vývojári
- 🇬🇧 Jazyk: **Angličtina**

---

### 🔧 **Chceš VEDIEŤ AKÉ ZMENY BOLI APLIKOVANÉ?**
👉 **[JETSON_PATCHES.md](JETSON_PATCHES.md)**
- ⏱️ Čas: 15 minút na čítanie
- 📝 Obsah: 8 konkrétnych patched s príkladmi
- ✅ Vhodný pre: Programátori

---

### 📋 **Chceš ZHRNUTIE VŠETKÉHO?**
👉 **[JETSON_DEPLOYMENT_SUMMARY.md](JETSON_DEPLOYMENT_SUMMARY.md)**
- ⏱️ Čas: 10 minút na čítanie
- 📝 Obsah: Prehľad + checklist
- ✅ Vhodný pre: Project managers

---

### ✅ **Chceš FINÁLNY STAV PROJEKTU?**
👉 **[JETSON_DEPLOYMENT_COMPLETE.md](JETSON_DEPLOYMENT_COMPLETE.md)**
- ⏱️ Čas: 10 minút na čítanie
- 📝 Obsah: Čo bolo hotovo + status
- ✅ Vhodný pre: Všetci

---

## 🛠️ PRACOVNÉ SÚBORY - POUŽITIE

### **jetson_test.py** - TESTER
```bash
# Spustite na Jetson aby ste testovali všetky závislosti
python3 jetson_test.py

# Očakávaný výstup:
# ✓ All 10 tests passed
# 🎉 READY FOR DEPLOYMENT!
```

---

### **run_visionpilot.sh** - LAUNCHER
```bash
# Spustite aplikáciu s automatickým setupom
chmod +x run_visionpilot.sh
./run_visionpilot.sh

# Alebo v background režimu
./run_visionpilot.sh background
```

---

### **requirements_jetson.txt** - PIP REQUIREMENTS
```bash
# Rýchla inštalácia všetkých závislostí
pip install -r requirements_jetson.txt

# POZNÁMKA: PyTorch musí byť inštalovaný oddelene!
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

---

### **config/platform_config.py** - KONFIGURÁCIA
```python
# Automaticky detekuje platformu a nastavuje parametre
from config.platform_config import IS_JETSON, get_serial_port

# Používa sa v gui.py:
if IS_JETSON or IS_LINUX:
    self._elm_port = "/dev/ttyUSB0"
```

---

## 🔄 INŠTALAČNÝ FLOW - KROK ZA KROKOM

```
1. Príprava Jetson (JetPack 6.0)
   └─ Dokumentácia: JETSON_SETUP_GUIDE.md

2. SSH pripojenie na Jetson
   └─ Príkaz: ssh ubuntu@jetson.local

3. Vytvorenie venv
   └─ Príkaz: python3.11 -m venv ~/visionpilot

4. Inštalácia PyTorch ARM64 ⚠️ KRITICKÉ!
   └─ Príkaz: pip install torch --index-url https://download.pytorch.org/whl/cu121
   └─ Bez toho GUI NEFUNGUJE!

5. Inštalácia ostatných balíčkov
   └─ Príkaz: pip install -r requirements_jetson.txt

6. Test všetkých závislostí
   └─ Príkaz: python3 jetson_test.py
   └─ Očakávané: 10/10 passed ✓

7. Spustenie GUI
   └─ Príkaz: export DISPLAY=:0 && python3 gui.py
   └─ Alebo: python3 gui.py (cez VNC)

8. Konfigurácia auto-startu (voliteľne)
   └─ Dokumentácia: JETSON_INSTALLATION_GUIDE_SK.md
```

---

## 📊 ZMENENÝ KÓD - PREHĽAD

### **Súbory Upravené** (2)
```
✅ gui.py
   - Platform detection
   - Serial port auto-detect
   - Windows-only winsound

✅ gpu_processing.py
   - CUDA device name fallback
```

### **Súbory Vytvorené** (11)
```
✅ config/platform_config.py       - Konfigurácia
✅ config/__init__.py              - Package init
✅ jetson_test.py                  - Tester
✅ run_visionpilot.sh              - Launcher
✅ requirements_jetson.txt         - Dependencies
✅ JETSON_SETUP_GUIDE.md           - Návod EN
✅ JETSON_INSTALLATION_GUIDE_SK.md - Návod SK
✅ JETSON_PATCHES.md               - Patches
✅ JETSON_DEPLOYMENT_SUMMARY.md    - Zhrnutie
✅ JETSON_QUICK_REFERENCE.md       - Cheat sheet
✅ JETSON_DEPLOYMENT_COMPLETE.md   - Finál stav
```

---

## 🎯 RÝCHLY NÁVOD - 3 KROKY NA JETSON

### **KROK 1: Príprava** (30 minút)
```bash
ssh ubuntu@jetson.local
sudo apt update && sudo apt upgrade -y
sudo reboot
```

### **KROK 2: Inštalácia** (15 minút)
```bash
python3.11 -m venv ~/visionpilot
source ~/visionpilot/bin/activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements_jetson.txt
```

### **KROK 3: Spustenie** (5 minút)
```bash
python3 jetson_test.py
export DISPLAY=:0
python3 gui.py
```

**HOTOVO! 🎉**

---

## ✅ KONTROLNÝ ZOZNAM

Pred spustením v produkcii:

- [ ] Prečítaný JETSON_QUICK_REFERENCE.md
- [ ] JetPack 6.0+ nainštalovaný a aktualizovaný
- [ ] Python 3.11 venv vytvorený
- [ ] PyTorch ARM64 wheels nainštalované
- [ ] Spustený `jetson_test.py` s všetkými ✓
- [ ] RealSense kamera testovaná a pripravená
- [ ] Serial port `/dev/ttyUSB0` pripravený
- [ ] GUI spustená úspešne
- [ ] Jetson Clocks povolený
- [ ] Monitoring nástrojov (`jtop`) nainštalovaný

---

## 🚨 KRITICKÉ VECI

### ⚠️ MUSÍ BYŤ VYKONANÉ

1. **PyTorch ARM64 wheels** - ÁNO, ÁNO, ÁNO!
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```
   Bez toho GUI nespustí!

2. **Serial Port Konfigurácia**
   - Automatická na Linux/Jetson: `/dev/ttyUSB0`
   - Bez dodatočného setupu!

3. **Display Setup** (pre GUI)
   - VNC recommended: `jetson.local:5900`
   - SSH s X11: `ssh -X ubuntu@jetson.local`

---

## 🔗 MAPOVANIE DOKUMENTOV

```
Úvod
  ↓
JETSON_QUICK_REFERENCE.md (5 min)
  ↓
Potrebuješ viac detailov?
  ├─ YES → JETSON_INSTALLATION_GUIDE_SK.md (30 min)
  └─ NO  → Preskočiť na inštaláciu
  ↓
Nevieš ako kód funguje?
  ├─ YES → JETSON_PATCHES.md (15 min)
  └─ NO  → Pokračuj
  ↓
Spustenie na Jetson
  ├─ jetson_test.py
  ├─ run_visionpilot.sh
  └─ python3 gui.py
  ↓
Hotovo! 🎉
```

---

## 📞 POMOC & PODPORA

### Ak máš problém
1. Spustite `jetson_test.py` - ukazuje kde je chyba
2. Pozrite sa na: JETSON_QUICK_REFERENCE.md → Common Issues
3. Skontrolujte: JETSON_INSTALLATION_GUIDE_SK.md → Riešenia

### Ak máš otázku
1. Hľadajte v dokumentoch (Ctrl+F)
2. Pozrite sa na relevantný návod
3. Skontrolujte externe zdroje v referencii

---

## 🏆 STATUS

| Komponent | Status | Dokument |
|-----------|--------|----------|
| Code Changes | ✅ | JETSON_PATCHES.md |
| Documentation | ✅ | Tento index |
| Testing Tools | ✅ | jetson_test.py |
| Launcher | ✅ | run_visionpilot.sh |
| Dependencies | ✅ | requirements_jetson.txt |
| Quick Guide | ✅ | JETSON_QUICK_REFERENCE.md |
| Detailed Guide SK | ✅ | JETSON_INSTALLATION_GUIDE_SK.md |
| Detailed Guide EN | ✅ | JETSON_SETUP_GUIDE.md |

---

## 📅 Dátum: 7. Apríla 2026

**Všetko je pripravené na nasadenie na Jetson Orin Nano! 🚀**

Ďakujeme za spoluprácu. Váš projekt je teraz cross-platform compatible!

