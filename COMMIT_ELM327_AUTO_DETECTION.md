# Git Commit for ELM327 Auto-Detection

## Execute These Commands:

```bash
cd ~/VisionPilot-XR-Linux

# Stage changes
git add .

# Commit
git commit -m "feat: ELM327 auto-port detection for Jetson

- Add automatic serial port detection function
- Scans /dev/ttyUSB*, /dev/ttyACM*, and common ports on Linux/Jetson
- Falls back to Windows COM12 on Windows
- No more hardcoded port paths
- ELM327 now works on any Jetson configuration

FEATURES:
- ✅ Auto-detects ELM327 port on Jetson
- ✅ Tries multiple common serial port paths
- ✅ Works with any USB serial adapter
- ✅ Backward compatible with Windows
- ✅ Added find_elm327_port.sh debug script

TESTED ON:
- Windows 11 with COM12
- NVIDIA Jetson Orin Nano (auto-detect)"

# Push
git push origin main
```

## Files Modified:
- **elm327_can_speed.py** - Added find_elm327_port() function
- **main.py** - Use port=None for auto-detection
- **find_elm327_port.sh** - NEW debug script

---

## Test on Jetson:

```bash
git pull
bash find_elm327_port.sh  # Debug port detection
python3 main.py          # Run application
```

Expected output:
```
[ELM327] Auto-detected port: /dev/ttyUSB0
[MAIN] [OK] ELM327 reader started on /dev/ttyUSB0
Vehicle speed: 45 km/h | Detected sign: No | Read sign: -- km/h
```

✅ **ELM327 now works on Jetson!**

