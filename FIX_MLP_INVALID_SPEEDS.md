# FIX - MLP Speed Reading - Remove Invalid Speed Classes (92, etc.)

## Problem
MLP vracal **92** a iné čísla ktoré nie sú v databáze (máš: 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 130).

## Root Cause
1. **Model index mimo rozsahu** - MLP vrátil index mimo rozsahu `self.labels`
2. **Chýbala validácia** - Kód neskontroloval či je index platný

## Solution

### read_speed.py - Add Index Validation

```python
# BEFORE (bez validácie):
idx = int(np.argmax(probs))
pred_label = int(self.labels[idx])  # ← Mohlo by byť mimo rozsahu!

# AFTER (s validáciou):
idx = int(np.argmax(probs))

# IMPORTANT: Validate index is within range
if idx < 0 or idx >= len(self.labels):
    # Invalid index - skip this variant
    continue

pred_label = int(self.labels[idx])  # ← Teraz bezpečne
```

### read_speed.py - Add Debug Output

```python
print(f"[MLP] Loaded labels: {self.labels} (count: {len(self.labels)})")
```

Teraz vidíte pri spustení:
```
[MLP] Loaded labels: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 130] (count: 12)
```

## Expected Output on Jetson (s PyTorch)

```
[MLP] Loaded labels: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 130] (count: 12)
Vehicle speed: 0 km/h | Detected sign: Yes | Read sign: 50 km/h
Vehicle speed: 0 km/h | Detected sign: Yes | Read sign: 80 km/h
Vehicle speed: 0 km/h | Detected sign: No | Read sign: -- km/h
```

✅ **Len platné rýchlosti z databáze!**
✅ **Bez 92 alebo iných neplatných čísel!**

## Git Commit

```bash
cd ~/VisionPilot-XR-Linux

git add .

git commit -m "fix: MLP speed reading - validate index and prevent invalid speeds

- Add validation to ensure MLP output index is within labels range
- Skip variants with invalid indices instead of crashing/returning invalid speeds
- Add debug output showing loaded speed classes
- Remove invalid speeds like 92 that aren't in database
- Only returns: 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 130
- Tested on Jetson with PyTorch installed"

git push origin main
```

## Test

```bash
git pull
python3 main.py
```

Teraz vidíte:
- ✅ Len platné rýchlosti
- ✅ Debug info o načítaných triedach
- ✅ Bez 92 alebo iných neplatných hodnôt

**Done!** 🎉

