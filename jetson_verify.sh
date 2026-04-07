#!/bin/bash

# VisionPilot XR - Python 3.8 Jetson Deployment Checklist
# Run this on Jetson AFTER installation to verify everything works

echo "🔍 VisionPilot XR - Python 3.8 Jetson Verification"
echo "===================================================="
echo ""

PASS=0
FAIL=0

# Helper functions
pass_test() {
    echo "  ✅ PASS: $1"
    ((PASS++))
}

fail_test() {
    echo "  ❌ FAIL: $1"
    ((FAIL++))
}

# Test 1: Python version
echo "1️⃣  Python Version"
PYVER=$(python --version 2>&1 | awk '{print $2}')
if [[ $PYVER == 3.8* ]]; then
    pass_test "Python 3.8.x detected ($PYVER)"
else
    fail_test "Wrong Python version: $PYVER (expected 3.8.x)"
fi
echo ""

# Test 2: PyTorch
echo "2️⃣  PyTorch Installation"
if python -c "import torch; print(f'PyTorch {torch.__version__}')" 2>/dev/null; then
    pass_test "PyTorch installed"
    if python -c "import torch; exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
        pass_test "CUDA available"
        GPU_NAME=$(python -c "import torch; print(torch.cuda.get_device_name(0))")
        echo "    GPU: $GPU_NAME"
    else
        fail_test "CUDA not available (CPU mode only)"
    fi
else
    fail_test "PyTorch not installed"
fi
echo ""

# Test 3: Core dependencies
echo "3️⃣  Core Dependencies"
DEPS=("numpy" "cv2 opencv" "scipy" "torch" "PyQt5" "serial pyserial" "psutil")

for dep in "${DEPS[@]}"; do
    IFS=' ' read -r module name <<< "$dep"
    if python -c "import $module" 2>/dev/null; then
        VERSION=$(python -c "import $module; print(getattr($module, '__version__', 'unknown'))" 2>/dev/null)
        pass_test "$name ($VERSION)"
    else
        fail_test "$name not installed"
    fi
done
echo ""

# Test 4: Project files
echo "4️⃣  Project Files"
FILES=("gui.py" "jetson_test.py" "requirements_jetson.txt" "install_jetson.sh" "quick_setup.sh")
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        pass_test "$file exists"
    else
        fail_test "$file missing"
    fi
done
echo ""

# Test 5: Serial port
echo "5️⃣  Serial Port Access (ELM327)"
if [ -c /dev/ttyUSB0 ]; then
    pass_test "/dev/ttyUSB0 available"
    PERMS=$(ls -l /dev/ttyUSB0 | awk '{print $1}')
    echo "    Permissions: $PERMS"
else
    echo "  ⚠️  /dev/ttyUSB0 not found (adapter not connected?)"
fi

if groups | grep -q dialout; then
    pass_test "User in dialout group"
else
    fail_test "User NOT in dialout group (run: sudo usermod -a -G dialout \$USER)"
fi
echo ""

# Test 6: Jetson detection
echo "6️⃣  Jetson Orin Nano Detection"
if [ -f /etc/nv_tegra_release ]; then
    pass_test "Running on NVIDIA Jetson"
    JETSON_INFO=$(cat /etc/nv_tegra_release | head -1)
    echo "    Info: $JETSON_INFO"
else
    fail_test "Not running on NVIDIA Jetson"
fi
echo ""

# Test 7: Virtual environment
echo "7️⃣  Virtual Environment"
if [ -n "$VIRTUAL_ENV" ]; then
    pass_test "Virtual environment active: $VIRTUAL_ENV"
else
    fail_test "Virtual environment NOT active (run: source ~/visionpilot/bin/activate)"
fi
echo ""

# Test 8: Python syntax
echo "8️⃣  Python Syntax Check"
FILES_TO_CHECK=("gui.py" "read_speed.py" "qt_read_sign.py" "qt_weather_detection.py")
SYNTAX_OK=true
for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$file" ]; then
        if python -m py_compile "$file" 2>/dev/null; then
            pass_test "$file syntax OK"
        else
            fail_test "$file syntax ERROR"
            SYNTAX_OK=false
        fi
    fi
done
echo ""

# Test 9: Display/X11 (optional)
echo "9️⃣  Display Server (Optional)"
if [ -n "$DISPLAY" ]; then
    pass_test "DISPLAY set to: $DISPLAY"
else
    echo "  ⚠️  DISPLAY not set (GUI won't work)"
    echo "    To enable: export DISPLAY=:0"
fi
echo ""

# Summary
echo "════════════════════════════════════════════════════"
echo "SUMMARY"
echo "════════════════════════════════════════════════════"
echo "  ✅ Passed: $PASS"
echo "  ❌ Failed: $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "🎉 ALL TESTS PASSED! Ready to run VisionPilot XR"
    echo ""
    echo "Next steps:"
    echo "  1. Test GUI: export DISPLAY=:0 && python gui.py"
    echo "  2. Or run tests: python jetson_test.py"
    echo "  3. Check performance: jtop"
    exit 0
else
    echo "⚠️  Some tests failed. Check above for details."
    echo ""
    echo "Common fixes:"
    echo "  - Python 3.8: python3.8 -m venv ~/visionpilot"
    echo "  - PyTorch: pip install torch==1.13.1 --index-url https://download.pytorch.org/whl/cu118"
    echo "  - Dialout: sudo usermod -a -G dialout \$USER && newgrp dialout"
    echo "  - Display: export DISPLAY=:0"
    exit 1
fi

