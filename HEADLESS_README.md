# VisionPilot XR - Headless CLI Mode (No GUI)

## Overview

**VisionPilot XR** now runs in **headless mode** - no GUI, just terminal output.

Features:
- ✅ Red nulling preprocessing
- ✅ Canny edge detection
- ✅ Ellipse detection
- ✅ MLP speed reading (from detected signs)
- ✅ ELM327 speed reading (from vehicle CAN-BUS)
- ✅ Real-time terminal output
- ✅ Performance statistics

---

## Installation on Jetson (4 Steps)

### Step 1: SSH to Jetson
```bash
ssh ubuntu@jetson.local
```

### Step 2: Install System Packages
```bash
sudo apt-get update
sudo apt-get install -y python3.8-venv python3.8-dev build-essential
```

### Step 3: Clone Project
```bash
cd ~
git clone https://github.com/nehovortake/VisionPilot-XR-Linux.git
cd VisionPilot-XR-Linux
```

### Step 4: Run Setup
```bash
bash jetson_fix.sh
```

This will automatically:
- ✅ Create Python 3.8 virtual environment
- ✅ Install PyTorch 1.13.1 (ARM64)
- ✅ Install all dependencies
- ✅ Start headless processing

---

## Running Headless Mode

### Option 1: Direct Command
```bash
source ~/visionpilot/bin/activate
cd ~/VisionPilot-XR-Linux
python visionpilot_headless.py
```

### Option 2: Using Start Script
```bash
bash ~/VisionPilot-XR-Linux/run_headless.sh
```

---

## Output Example

```
[INIT] VisionPilot XR - Headless Mode (No GUI)
============================================================
[INIT] Loading modules...
✓ ImageProcessor loaded
✓ Speed reader loaded
✓ RealSense camera loaded
✓ ELM327 reader loaded

[CAMERA] Initializing camera...
✓ RealSense camera initialized

[PROCESSOR] Initializing image processor...
✓ Image processor initialized
  - Red nulling: ENABLED
  - Canny edge: ENABLED
  - Ellipse detection: ENABLED

[SPEED] Initializing speed reader...
✓ Speed reader initialized

[ELM327] Initializing ELM327 reader...
✓ ELM327 reader initialized (port: /dev/ttyUSB0)

[START] Processing frames...
============================================================
Press Ctrl+C to stop

[Frame 000005] Process: 12.3ms | ELM327: 65.5 km/h | Detected: 80 km/h
[Frame 000010] Process: 11.8ms | ELM327: 66.2 km/h | Detected: 80 km/h
[Frame 000015] Process: 12.1ms | ELM327: 67.0 km/h | Detected: 65 km/h
[Frame 000020] Process: 12.0ms | ELM327: 68.5 km/h
...
```

---

## Terminal Output Explained

| Output | Meaning |
|--------|---------|
| `[INIT]` | Initialization phase |
| `[CAMERA]` | Camera detection and setup |
| `[PROCESSOR]` | Image processor pipeline |
| `[SPEED]` | Speed reading model |
| `[ELM327]` | CAN-BUS speed reader |
| `[Frame XXXXXX]` | Processing output |
| `Process: 12.3ms` | Image processing time |
| `ELM327: 65.5 km/h` | Speed from vehicle CAN-BUS |
| `Detected: 80 km/h` | Speed from sign/MLP detection |

---

## Controls

| Key | Action |
|-----|--------|
| `Ctrl+C` | Stop processing |

---

## Performance Tips

### Reduce Output Spam
Edit `visionpilot_headless.py` line ~220:
```python
if frame_count % 5 == 0:  # Change 5 to 10, 20, etc. for less output
```

### Monitor Jetson Performance
Open another terminal:
```bash
jtop
```

---

## Troubleshooting

### Camera Not Found
```
✗ RealSense failed: ...
[FALLBACK] Trying OpenCV webcam...
```
- Check if RealSense camera is connected
- USB issues? Try different USB port

### ELM327 Not Found
```
✗ ELM327 error: ...
  (This is OK if ELM327 adapter is not connected)
```
- ELM327 adapter is optional
- Processing continues without vehicle speed

### Speed Reader Error
```
✗ Speed reader error: ...
```
- Check if `dataset/mlp_speed_model.pt` exists
- Run `python jetson_test.py` to diagnose

### ImportError
```
ModuleNotFoundError: No module named 'realsense'
```
- Some modules are optional
- Processing continues with available modules

---

## File Structure

```
~/VisionPilot-XR-Linux/
├── visionpilot_headless.py    ← Main headless script
├── run_headless.sh            ← Quick start script
├── jetson_fix.sh              ← Installation script
├── image_processing.py        ← Red nulling, Canny, Ellipse
├── read_speed.py              ← MLP speed reading
├── elm327_can_speed.py        ← Vehicle speed (CAN-BUS)
└── [other files]
```

---

## Logs & Debugging

### Full Debug Output
```bash
python -u visionpilot_headless.py 2>&1 | tee visionpilot.log
```

### Check Dependencies
```bash
python -c "
import cv2, numpy, torch, PyQt5
print('✓ All dependencies OK')
"
```

### Test Camera
```bash
python -c "
import cv2
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
print(f'Camera OK: {ret}, Frame shape: {frame.shape}')
"
```

---

## Next Steps

1. **Run installation**:
   ```bash
   bash jetson_fix.sh
   ```

2. **Start processing**:
   ```bash
   source ~/visionpilot/bin/activate
   python visionpilot_headless.py
   ```

3. **Monitor performance**:
   ```bash
   jtop
   ```

4. **View logs** (in another terminal):
   ```bash
   tail -f visionpilot.log
   ```

---

**Status**: ✅ Ready for Jetson Headless Deployment

