# PyTorch TLS Fix - Shell Method

## Problem
LD_PRELOAD sa musí nastaviť **v shell environment** predtým ako sa spustí Python.

## Solution: Use Shell Wrapper

### Method 1: Direct command (copy-paste)

Na Jetsone spusti:

```bash
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1 && \
cd ~/Desktop/VisionPilot-XR-Linux && \
python3 test_mlp_live.py
```

### Method 2: Using bash script

```bash
bash ~/Desktop/VisionPilot-XR-Linux/run_mlp_test.sh
```

### Method 3: Permanent fix in .bashrc

```bash
echo 'export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1' >> ~/.bashrc
source ~/.bashrc

# Now every command has LD_PRELOAD set
python3 test_mlp_live.py
```

## Expected Output

```
[WRAPPER] LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1

[TEST] Direct MLP Test on Live Camera Feed
✓ RealSense available
✓ PyTorch and PerceptronSpeedReader loaded
✓ Model loaded: 12 classes

[TEST] Capturing frames and testing MLP...

[FRAME 1] ✓ Predicted: 50 km/h
[FRAME 2] ✓ Predicted: 50 km/h
[FRAME 3] - No prediction

✓ MLP IS WORKING!
  Predicted speeds: [50, 50, 60, 50]
```

---

**Try Method 1 on Jetson now!** 🎯

Copy-paste this:
```bash
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1 && cd ~/Desktop/VisionPilot-XR-Linux && python3 test_mlp_live.py
```

