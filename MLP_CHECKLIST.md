# ✅ COMPLETE CHECKLIST - MLP SPEED READING

## 1. HARDWARE & OS
- ✅ NVIDIA Jetson Orin Nano
- ✅ Ubuntu 20.04
- ✅ Python 3.8.10

## 2. PYTHON PACKAGES (MUST INSTALL)
```bash
pip install torch==2.1.0 -f https://download.pytorch.org/whl/torch_stable.html
pip install torchvision==0.16.0 torchaudio==2.1.0 -f https://download.pytorch.org/whl/torch_stable.html
pip install numpy==1.21.6
pip install opencv-python==4.6.0.66
pip install pyserial==3.5
```

**OVERÍŤ NA JETSONE:**
```bash
python3 -c "import torch; print(torch.__version__)"  # Must be 2.1.0
python3 -c "import cv2; print(cv2.__version__)"
python3 -c "import numpy; print(numpy.__version__)"  # Must be 1.21.6
```

## 3. MODEL FILE
- ✅ Musí existovať: `~/Desktop/VisionPilot-XR-Linux/dataset/mlp_speed_model_dataset_split.pt`
- ✅ Má byť tam už z projektu
- **OVERÍŤ:** `ls -lh ~/Desktop/VisionPilot-XR-Linux/dataset/mlp_speed_model_dataset_split.pt`

## 4. CODE FILES (MUSIA BYŤ SPRÁVNE)
- ✅ `read_speed.py` - **PRESNE ako v Windows verzii** (v attachmente)
- ✅ `main.py` - s LD_PRELOAD fixom
- ✅ `image_processing.py` - musí volať `speed_reader.predict_from_crop(crop)`

## 5. ENVIRONMENT VARIABLES
- ✅ `LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1` - **POVINNÝ!**

## 6. DETEKCIA ZNAČKY
- ✅ Ellipse detection musí fungovať (vidíš zelenú elipsu na monitore)
- ✅ Crop musí byť extrahovaný správne
- ✅ Crop sa musí poslať do `predict_from_crop()`

## 7. MLP KLASIFIKÁCIA
- ✅ Model musí byť načítaný: `[MLP] Loaded | classes=[10,20,30,40,50,60,70,80,90,100,110,130]`
- ✅ Softmax prah: 0.9 (zamietne slabé predikcie)
- ✅ Margin prah: 0.35 (confidence)
- ✅ Vote threshold: 4 (stabilizácia)

## 8. OUTPUT
- ✅ Terminal: `Vehicle speed: 0 km/h | Detected sign: Yes | Read sign: 110 km/h`
- ✅ GUI: Vyznačená elipsa, "Detected sign: Yes", "Read sign: 110 km/h"

---

## DIAGNOSTIKA - AK NEFUNGUJE

### Scenár 1: "Read sign: --" s "Detected sign: Yes"
**Problém:** MLP sa nevolá alebo vráti None
**Riešenie:**
```bash
# Overíť PyTorch
python3 -c "import torch; print('PyTorch OK')"

# Overíť model file
ls -lh ~/Desktop/VisionPilot-XR-Linux/dataset/mlp_speed_model_dataset_split.pt

# Overíť read_speed.py
grep "class PerceptronSpeedReader" ~/Desktop/VisionPilot-XR-Linux/read_speed.py
```

### Scenár 2: "PyTorch not installed"
**Problém:** PyTorch nie je nainštalovaný
**Riešenie:**
```bash
pip install torch==2.1.0 -f https://download.pytorch.org/whl/torch_stable.html
```

### Scenár 3: "cannot allocate memory in static TLS block"
**Problém:** LD_PRELOAD nie je nastavený
**Riešenie:**
```bash
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1
python3 main.py
```

### Scenár 4: Detekcia nefunguje vôbec
**Problém:** Ellipse detection je vypnutý
**Riešenie:**
```bash
# Overíť v main.py
grep "Ellipse Detection" ~/Desktop/VisionPilot-XR-Linux/main.py
# Musí byť: "Ellipse Detection: ENABLED"
```

---

## ČISTY GIT PULL NA JETSONE

```bash
cd ~/Desktop/VisionPilot-XR-Linux
git fetch origin
git reset --hard origin/main
git pull origin main
```

---

## DEFINÍTÍVNY TEST PRÍKAZ

```bash
cd ~/Desktop/VisionPilot-XR-Linux && \
python3 -c "
import torch
import cv2
import numpy
from pathlib import Path

print('✓ PyTorch', torch.__version__)
print('✓ CV2', cv2.__version__)
print('✓ NumPy', numpy.__version__)

# Test model load
from read_speed import PerceptronSpeedReader
reader = PerceptronSpeedReader()
print('✓ MLP loaded')
print('  Labels:', reader.labels)
print('  Min softmax prob:', reader.min_softmax_prob)
print('  Min margin:', reader.min_margin)
print('  Min votes:', reader.min_votes)
"
```

---

## FINAL EXECUTION

```bash
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1
cd ~/Desktop/VisionPilot-XR-Linux
python3 main.py
```

**Keď vidíš značku:**
- Terminal: `Read sign: 110 km/h` ✅
- GUI: Vyznačená elipsa + "Detected sign: Yes" ✅

---

## ČOHO NEMÁŠ TERAZ MUSÍŠ MAŤ

1. ✅ PyTorch 2.1.0
2. ✅ Správny read_speed.py (z Windows verzije)
3. ✅ Model file (mlp_speed_model_dataset_split.pt)
4. ✅ LD_PRELOAD nastavený
5. ✅ Git pull na čiste

**Bez týchto VŠETKÝCH 5 VECÍ = NEBUDE FUNGOVAŤ!**

