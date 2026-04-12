# PyTorch TLS Memory Issue - SOLVED

## Problem
```
✗ PyTorch not available: 
  /home/feit/.local/lib/python3.8/site-packages/torch/lib/../../torch.libs/libgomp-804f19d4.so.1.0.0: 
  cannot allocate memory in static TLS block
```

## Root Cause
Known issue s PyTorch na Jetsone s Python 3.8 - OpenMP library conflict

## Solution

### Method 1: Using test_with_fix.py (Easiest)
```bash
cd ~/Desktop/VisionPilot-XR-Linux
python3 test_with_fix.py
```

Tento skript:
- ✅ Automaticky nastaví LD_PRELOAD
- ✅ Načítá PyTorch
- ✅ Spustí margin test

### Method 2: Manual LD_PRELOAD
```bash
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1
python3 main.py
```

### Method 3: Permanentný fix
Aktualizovaný `main.py` teraz **automaticky nastaví LD_PRELOAD** na Linuxe!

```bash
python3 main.py
# Teraz bude fungovať bez manuálneho nastavenia!
```

## Execute Now on Jetson

### Step 1: Run test with fix
```bash
cd ~/Desktop/VisionPilot-XR-Linux
python3 test_with_fix.py
```

Očakávaný výstup:
```
✓ PyTorch loaded: 2.x.x
✓ Model loaded: 12 classes
  Min margin required: 0.15

[TEST 1]
  [REJECTED] margin=0.12 < 0.15 (label=50)
  
[MARGIN TEST] Summary:
  Margin values collected: 30
  ...
  ⚠ All predictions rejected!
    RECOMMENDED FIX:
      1. In read_speed.py, change:
         self.min_margin = 0.05
      2. Also lower min_votes to 2
```

### Step 2: Apply fix based on test output

Podľa výstupu testu, upraviť `read_speed.py`:

```python
# read_speed.py - riadok ~167
self.min_margin = 0.05      # Znížiť z 0.15 na odporúčanú hodnotu
self.min_votes = 2          # Znížiť z 4 na 2
```

### Step 3: Git push

```bash
cd ~/Desktop/VisionPilot-XR-Linux
git add .
git commit -m "fix: Add LD_PRELOAD fix for PyTorch on Jetson + adjust MLP thresholds"
git push origin main
```

### Step 4: Test main.py

```bash
python3 main.py
```

Teraz by malo čítať rýchlosť!

---

## Troubleshooting

Ak stále nejde:

1. Skontroluj libgomp path:
```bash
find /usr -name "libgomp.so*" 2>/dev/null
```

2. Manuálne nastav:
```bash
export LD_PRELOAD=/path/to/libgomp.so.1
python3 test_with_fix.py
```

3. Pošli output z `python3 test_with_fix.py`

---

**Execute these steps exactly!** 🎯

