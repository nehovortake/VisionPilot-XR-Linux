# PyTorch TLS Problem - FINAL SOLUTION

## Current Issue
PyTorch sa nenačítava na Jetsone kvôli OpenMP TLS memory problému.

## Opcia 1: Skip MLP, Use Vehicle Speed from ELM327

Ak chceš aby fungovala aplikácia aj bez MLP:
- ✅ Detekcia značky (ellipse detection) - FUNGUJE
- ✅ Rýchlosť vozidla z ELM327 - FUNGUJE (keď je pripojený)
- ❌ Čítanie značky (MLP) - Netreba

## Riešenie: Disable MLP in main.py

### Edit main.py:

Find line kde sa volá speed_reader:
```python
# Nahradiť tento kód:
if self.enable_ellipse and edges is not None:
    out, ellipse_crops = detect_ellipses_fast(edges, original)
    # ... process ellipses ...
    for det in ellipse_crops:
        self.sign_detected_this_frame = True
        # Skip MLP - just mark as detected
        # Don't call speed_reader.predict_from_crop()
```

### Result:
```
Vehicle speed: 45 km/h | Detected sign: Yes | Read sign: -- km/h
```

- ✅ Vehicle speed - z ELM327
- ✅ Detected sign - Yes/No z detekcie elipsy
- ✅ Read sign - -- (bez MLP)

## Opcia 2: Use Shell Wrapper

Na Jetsone:
```bash
bash ~/Desktop/VisionPilot-XR-Linux/launch_jetson.sh
```

Tento script nastaví LD_PRELOAD + PYTHONHASHSEED pre PyTorch.

## Opcia 3: Install PyTorch from Source (Advanced)

```bash
pip install torch --no-cache-dir
# or
pip install torch==2.0.0  # Staršia verzia
```

---

## RECOMMENDED: Opcia 1 + Opcia 2

1. Skús shell wrapper: `bash launch_jetson.sh`
2. Ak stále nefunguje PyTorch, oprav image_processing.py aby skipol MLP

To bude fungovať s vehicle speed z ELM327!

---

**Skúš najprv: bash ~/Desktop/VisionPilot-XR-Linux/launch_jetson.sh** 🎯

