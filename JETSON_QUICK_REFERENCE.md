# VisionPilot XR - Jetson Quick Reference

## 🚀 Start Application (30 seconds)

```bash
cd VisionPilot-XR-Linux
python3 main.py
```

**That's it!** No configuration needed.

---

## 📋 What Happens on Startup

1. **Auto-detects Jetson** → Shows "Device: NVIDIA Jetson (Orin Nano)"
2. **Initializes Camera** → 1920x1080 @ 30 FPS RealSense D415
3. **Loads MLP Model** → Speed classification network
4. **Starts ELM327 Reader** → Vehicle speed from CAN bus
5. **Opens GUI Window** → Live camera with detections
6. **Terminal Output** → Vehicle speed, detected sign, read value

---

## 🎨 Terminal Output Format

```
Vehicle speed: 45 km/h | Detected sign: Yes | Read sign: 50 km/h
```

Updates only when values change (not spammy).

---

## 🎮 Controls

- **GUI Window**
  - Press **ESC** to stop
  - Camera feed updates in real-time
  - Green circle shows detected speed sign

- **Terminal**
  - Press **Ctrl+C** to stop
  - Shows vehicle speed and detected sign status

---

## 📊 Performance

### Jetson Orin Nano
- **FPS**: 25-30 typical
- **CPU**: 40-60% (tegrastats reported)
- **Memory**: ~200MB Python process
- **Frame Time**: 30-40ms average

---

## 🔧 Troubleshooting

### "Could not open port '/dev/ttyUSB0'"
**Cause**: ELM327 device not connected
**Solution**: Connect ELM327 adapter (optional, app continues without it)

### "RealSense not available"
**Cause**: Camera not plugged in
**Solution**: Connect Intel RealSense D415 camera

### "GUI fails to open"
**Cause**: No display connected
**Solution**: App runs in headless mode, terminal output still works

### "No module named 'torch'"
**Cause**: PyTorch not installed
**Solution**: `pip install -r requirements_jetson.txt`

---

## 📁 Important Directories

```
VisionPilot-XR-Linux/
├── dataset/              ← Speed sign images (training)
├── gui_assets/           ← UI resources
├── CAN_logs/             ← Vehicle speed logs
├── log_files/            ← Performance logs
└── main.py               ← Start here
```

All paths are **relative**, so you can run from anywhere.

---

## 🔄 Common Tasks

### Verify Setup
```bash
bash verify_jetson_setup.sh
```

### Check Python Version
```bash
python3 --version  # Should be 3.8+
```

### Install Missing Dependencies
```bash
pip install -r requirements_jetson.txt
```

### Train New MLP Model
```bash
python3 train_mlp_speed.py
```

### Generate Training Dataset
```bash
python3 generate_speed_fonts_dataset.py
```

### Analyze Performance
```bash
# Auto-generated graph on exit
# Saved to: log_files/cpu_graph_YYYY-MM-DD_HH-MM-SS.png
```

---

## 💾 Auto-Saved Files

### Performance Logs
```
log_files/perf_log_2026-04-12_15-30-45.txt
log_files/cpu_graph_2026-04-12_15-30-45.png
```

### CAN Bus Logs
```
CAN_logs/elm327_log_2026-04-12_15-30-45.csv
```

---

## 🌍 Platform Detection

| Platform | Auto-Detected | Port | CPU Monitor |
|----------|---------------|------|-------------|
| Windows | ✅ | COM12 | psutil |
| Linux | ✅ | /dev/ttyUSB0 | psutil |
| Jetson | ✅ | /dev/ttyUSB0 | tegrastats |

---

## 📖 Documentation

- **JETSON_DEPLOYMENT.md** - Full deployment guide
- **JETSON_DEPLOYMENT_CHECKLIST.md** - Setup verification
- **JETSON_READY_SUMMARY.md** - This summary
- **GIT_PUSH_JETSON.md** - Git workflow

---

## ✅ Pre-Flight Checklist

Before running on Jetson:

- [ ] Python 3.8 or higher installed
- [ ] Intel RealSense D415 camera connected
- [ ] Dependencies installed (`pip install -r requirements_jetson.txt`)
- [ ] Display connected OR X11 forwarding configured
- [ ] ELM327 CAN adapter connected (optional)

---

## 🚀 One-Command Start

```bash
cd VisionPilot-XR-Linux && python3 main.py
```

---

## 📞 Support

### Check Jetson Info
```bash
cat /sys/devices/virtual/dmi/id/board_name
```

### Check GPU Status
```bash
tegrastats --interval 500 --count 10
```

### Check Available Ports
```bash
ls /dev/ttyUSB*
```

---

## 💡 Tips

1. **Stabilize FPS**: Close other applications
2. **Reduce CPU**: Lower camera resolution in `realsense.py` (optional)
3. **View Logs**: `tail -f log_files/perf_log_*.txt`
4. **Stop Cleanly**: Press ESC in GUI or Ctrl+C in terminal
5. **CPU Graph**: Automatically saved on exit as PNG

---

## ⚡ Performance Optimization

### For Maximum FPS:
```python
# Already optimized in main.py
# - GPU acceleration enabled
# - Fast ellipse detection enabled
# - Efficient frame processing
```

### For Lower CPU:
```bash
# Monitor tegrastats in another terminal
tegrastats --interval 1000
```

---

*Last Updated: April 12, 2026*
*Ready for: NVIDIA Jetson Orin Nano + Python 3.8*


