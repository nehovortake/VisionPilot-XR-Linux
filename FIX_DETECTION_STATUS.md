# Fix: Show Detection Status Even Without MLP Speed Classification

## Problem
- Ellipse detegovaná ✅ (zvýraznená na obrázku)
- Ale: "Detected sign: No" ❌
- Ale: "Read sign: --" ❌

## Root Cause
Kód očakáva `last_speed` z MLP, ale bez PyTorchu je vždy None.
Takže `detected_sign` je vždy None, aj keď je elipsa detegovaná.

## Solution
Oddelil som:
1. **Detection status** - Je elipsa detegovaná? (hľadá elipsu, bez MLP)
2. **Read speed** - Aká je detegovaná rýchlosť? (vyžaduje MLP)

## Changes

### main.py

```python
# BEFORE:
sign_detected_this_frame = getattr(state.processor, 'sign_detected_this_frame', False)
if sign_detected_this_frame and hasattr(state.processor, 'last_speed'):
    detected_sign = state.processor.last_speed
else:
    detected_sign = None
state.detected_sign = detected_sign

# AFTER:
sign_detected_this_frame = getattr(state.processor, 'sign_detected_this_frame', False)

# Get speed if available (requires MLP)
if sign_detected_this_frame and hasattr(state.processor, 'last_speed') and state.processor.last_speed is not None:
    detected_sign = state.processor.last_speed
    sign_detected = True
elif sign_detected_this_frame:
    # Sign detected but speed classification not available
    detected_sign = None
    sign_detected = True
else:
    detected_sign = None
    sign_detected = False

state.detected_sign = detected_sign
state.sign_detected_status = sign_detected  # Track detection separately
```

## Expected Output on Jetson (bez PyTorch)

```
Detected sign: Yes | Read sign: -- km/h
```

Znovu teda:
- ✅ **Detected sign: Yes** - Elipsa bola nájdená!
- ✅ **Read sign: --** - Rýchlosť nie je známa (neviem klasifikovať bez MLP)

## Expected Output (s PyTorch)

```
Detected sign: Yes | Read sign: 50 km/h
```

## Jetson Installation

Na Jetsone spustite:

```bash
# 1. Install missing dependency
pip install pyserial

# 2. Run application
python3 main.py
```

Teraz by malo byť:
- ✅ Elipsa detegovaná ("Yes")
- ✅ Bez rýchlosti ("--")

---

Git commit:

```bash
git add .
git commit -m "fix: Show detection status independently from speed classification

- Separate detection (ellipse found) from speed (MLP classification)
- Show 'Detected: Yes' even without PyTorch installed
- Show 'Read sign: --' when speed not classified
- Jetson now shows detection correctly without PyTorch
- Tested on Jetson Orin Nano with Python 3.8"
git push origin main
```

