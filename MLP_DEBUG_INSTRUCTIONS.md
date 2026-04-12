# MLP Debug - Complete Test Instructions

## Problem
Rýchlosť sa nečíta aj keď je značka detegovaná (Read sign: --)

## Root Cause Analysis
Vytvoril som dva test skripty na zistenie prečo:

### Test 1: `test_mlp_debug.py`
Komplexný test všetkých krokov:
```bash
python3 test_mlp_debug.py
```

Skontroluje:
- Či sa PyTorch načítava
- Či sa model načítava s správnymi triedami
- Preprocessing na syntetickej elipse
- MLP predikcia
- Real-time camera feed

### Test 2: `test_margin_debug.py` (IMPORTANT!)
Skúma **margin values** - to je dôvod prečo sa zamietajú predikcie:
```bash
python3 test_margin_debug.py
```

Vykonáva 10 testov a ukazuje:
- Koľko margin je **pod prahom**
- Koľko predpovedí bolo **zahodených**
- Odporúčené nové hodnoty pre min_margin

## Jak Spustiť na Jetsone

```bash
cd ~/Desktop/VisionPilot-XR-Linux

# Test 1 - Všetky komponenty
python3 test_mlp_debug.py

# Test 2 - Margin analýza (DÔLEŽITÉ!)
python3 test_margin_debug.py

# Podľa výstupu Test 2, aktualizuj read_speed.py:
# Ak vidíš "Values below threshold: 10" a "Accepted: 0"
# Znížiť min_margin!
```

## Očakávaný Output

### test_mlp_debug.py
```
✓ PyTorch X.X
✓ PerceptronSpeedReader imported
✓ Model loaded
  Classes: [10, 20, 30, ...]
✓ Created synthetic crop
✓ Variant 'default': (64, 64)
✓ Variant 'three_pad': (64, 64)
✓ Predictions: [None, None, None, ...]
  ↑ Ak všetky sú None, problém je margin!
```

### test_margin_debug.py
```
[TEST 1]
  [REJECTED] margin=0.12 < threshold=0.15 (label=50)

[MARGIN TEST] Summary:
  Margin values collected: 30
  Margin min: 0.08
  Margin max: 0.25
  Margin threshold: 0.15
  Values below threshold: 22
  
  Accepted predictions: 0
  Rejected predictions: 10

⚠ All predictions rejected!
  Possible fixes:
    1. Lower min_margin from 0.15 to 0.10
    2. Lower min_votes from 4 to 1
```

## Ak Je Problém Margin

Oprav `read_speed.py`:

```python
# BEFORE (zamieta všetko):
self.min_margin = 0.15

# AFTER (čítava všetko):
self.min_margin = 0.10  # Alebo nižšie podľa testu
self.min_votes = 2      # Znížiť aj votes
```

## Git Commit

Keď test ukáže čo je problém:

```bash
cd ~/VisionPilot-XR-Linux
git add .
git commit -m "fix: Adjust MLP margin threshold based on debug analysis"
git push origin main
```

---

**Follow these steps exactly and report the output!** 🎯

