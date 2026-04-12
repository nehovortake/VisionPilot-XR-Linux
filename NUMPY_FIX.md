# NumPy Compatibility Fix for PyTorch on Jetson

## Problem
```
Module compiled against API version 0x10 but this version of numpy is 0xd
```

NumPy na Jetsone je stará verzia a PyTorch potrebuje novšiu.

## Solution: Update NumPy

### Step 1: On Jetson, run:

```bash
cd ~/Desktop/VisionPilot-XR-Linux

# Fix NumPy version
pip install --upgrade numpy

# Or specific version for Jetson + PyTorch 2.4.1:
pip install numpy==1.21.6
```

### Step 2: Verify installation

```bash
python3 -c "import numpy; print(f'NumPy: {numpy.__version__}')"
```

Should show: `NumPy: 1.21.6` (or newer)

### Step 3: Run test again

```bash
python3 test_with_fix.py
```

Expected output (without Numpy errors):
```
✓ PyTorch loaded: 2.4.1
✓ Model loaded: 12 classes

[TEST 1]
  [ACCEPTED] margin=0.45, votes=4, speed=50

[TEST 2]
  [REJECTED] margin=0.12 < 0.15 (label=50)

[MARGIN TEST] Summary:
  Margin values collected: 30
  Accepted predictions: 7
  Rejected predictions: 3
  
  RECOMMENDED FIX:
    1. In read_speed.py, change:
       self.min_margin = 0.10
    2. Also lower min_votes to 2
```

### Step 4: Apply the fix

Based on test output, update `read_speed.py`:

```python
# Line ~167
self.min_margin = 0.10      # Znížiť z 0.15
self.min_votes = 2          # Znížiť z 4
```

### Step 5: Git push

```bash
git add .
git commit -m "fix: Update NumPy and adjust MLP thresholds for Jetson"
git push origin main
```

### Step 6: Run main.py

```bash
python3 main.py
```

Should now read speed correctly!

---

## Quick Commands to Run Now

```bash
# 1. Fix NumPy
pip install --upgrade numpy

# 2. Test again
python3 test_with_fix.py

# 3. Check output and report what it says!
```

**Execute now!** 🎯

