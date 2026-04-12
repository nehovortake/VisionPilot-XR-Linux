# ⚠️ PYTORCH NIE JE NAINŠTALOVANÝ NA JETSONE!

## Problem

```
[read_speed] Warning: PyTorch not installed, speed reader will be disabled
```

**Read sign je "--" pretože PyTorch neexistuje!**

Bez PyTorchu nie je možné nič - MLP dummy klasa len vracia None.

## Riešenie: Nainštalovať PyTorch na Jetsone

### Na Jetsone Spusti:

```bash
# Stiahnúť a pustiť inštalačný skript
cd ~/Desktop/VisionPilot-XR-Linux
bash install_pytorch_jetson.sh
```

Alebo manuálne:

```bash
pip install torch==2.1.0 -f https://download.pytorch.org/whl/torch_stable.html
pip install torchvision==0.16.0 torchaudio==2.1.0 -f https://download.pytorch.org/whl/torch_stable.html
```

### Overenie či je nainštalovaný:

```bash
python3 -c "import torch; print(torch.__version__)"
```

Musí vypísať: `2.1.0` alebo novšie

## Potom Spusti:

```bash
cd ~/Desktop/VisionPilot-XR-Linux
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1
python3 main.py
```

## Očakávaný Výstup (s PyTorchom)

```
[MLP] Loaded | classes=[10,20,30,40,50,...] | img=64

[MLP-DEBUG] Variant 'default': prob=0.950, margin=0.456, label=110
[MLP-DEBUG] Variant 'three_pad': prob=0.920, margin=0.234, label=110
[MLP-DEBUG] Best: label=110, prob=0.950, margin=0.456
[MLP-DEBUG] ACCEPTED: speed=110 km/h (votes=4)

Vehicle speed: 0 km/h | Detected sign: Yes | Read sign: 110 km/h
```

---

## SPUSTI TERAZ NA JETSONE:

```bash
bash ~/Desktop/VisionPilot-XR-Linux/install_pytorch_jetson.sh
```

**Potom pošli output!** 🎯

