#!/bin/bash
#!/bin/bash

# VisionPilot XR - JETSON ORIN NANO - FULL INSTALLATION SCRIPT (Python 3.8)
#
# Táto schéma automaticky inštaluje VisionPilot na Jetson Orin Nano s Python 3.8
#
# Predpoklady:
#   - JetPack 6.0+ nainštalovaný
#   - SSH prístup na Jetson
#   - Internet pripojenie
#   - Python 3.8+ dostupný
#
# Použitie:
#   ssh ubuntu@jetson.local
#   bash install_jetson.sh
#
# Alebo na Windows (PowerShell):
#   scp -r * ubuntu@jetson.local:~/visionpilot/
#   ssh ubuntu@jetson.local
#   cd ~/visionpilot
#   bash install_jetson.sh

set -e  # Exit on any error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Logging functions
log_info() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_header() { echo -e "\n${CYAN}╔════════════════════════════════════════════════════╗${NC}"; echo -e "${CYAN}║  $1${NC}"; echo -e "${CYAN}╚════════════════════════════════════════════════════╝${NC}"; }

# Detect Python version
if command -v python3.8 &> /dev/null; then
    PYTHON_CMD="python3.8"
    PYTHON_VER="3.8"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VER=$($PYTHON_CMD --version | awk '{print $2}')
else
    log_error "Python 3.8+ not found!"
    exit 1
fi

log_info "Using Python: $PYTHON_CMD ($PYTHON_VER)"

# Check OS
if [ "$(uname -s)" != "Linux" ]; then
    log_error "This script runs on Linux only (you are on $(uname -s))"
    exit 1
fi

# Check if Jetson
if [ ! -f "/etc/nv_tegra_release" ]; then
    log_warn "This script is optimized for Jetson, but you are not running on Jetson"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

VENV_PATH="$HOME/visionpilot"

log_header "VisionPilot XR - Jetson Installation (Python 3.8)"

# ============================================================
# PHASE 1: System Update
# ============================================================

log_header "PHASE 1/5: System Update"

log_info "Updating package lists..."
sudo apt-get update

log_info "Upgrading packages..."
sudo apt-get upgrade -y

log_info "Installing build tools..."
sudo apt-get install -y \
    build-essential \
    cmake \
    git \
    python3.8-dev \
    python3.8-venv \
    libpython3.8-dev \
    udev \
    libatlas-base-dev \
    libjasper-dev \
    libtiff-dev \
    libwebp-dev

log_info "Phase 1 complete ✓"

# ============================================================
# PHASE 2: Virtual Environment (Python 3.8)
# ============================================================

log_header "PHASE 2/5: Python 3.8 Virtual Environment"

if [ -d "$VENV_PATH" ]; then
    log_warn "Virtual environment already exists at $VENV_PATH"
    read -p "Remove and recreate? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_PATH"
        log_info "Creating new virtual environment with Python 3.8..."
        python3.8 -m venv "$VENV_PATH"
    fi
else
    log_info "Creating new virtual environment with Python 3.8..."
    python3.8 -m venv "$VENV_PATH"
fi

# Activate venv
source "$VENV_PATH/bin/activate"
log_info "Virtual environment activated ✓"

# Upgrade pip
log_info "Upgrading pip, setuptools, wheel..."
pip install --upgrade pip setuptools wheel

log_info "Phase 2 complete ✓"

# ============================================================
# PHASE 3: PyTorch ARM64 (Python 3.8 Compatible)
# ============================================================

log_header "PHASE 3/5: PyTorch ARM64 (CRITICAL - Python 3.8 Version)"

log_warn "Installing PyTorch 1.13.1 (Python 3.8 compatible)..."
log_info "This may take 5-10 minutes..."

pip install torch==1.13.1 torchvision==0.14.1 torchaudio==0.13.1 \
    --index-url https://download.pytorch.org/whl/cu118

# Verify PyTorch
log_info "Verifying PyTorch installation..."
python -c "
import torch
print(f'  PyTorch version: {torch.__version__}')
print(f'  CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'  CUDA device: {torch.cuda.get_device_name(0)}')
    print(f'  CUDA version: {torch.version.cuda}')
else:
    print('  WARNING: CUDA not available - CPU mode only')
"

log_info "Phase 3 complete ✓"

# ============================================================
# PHASE 4: Dependencies (Python 3.8)
# ============================================================

log_header "PHASE 4/5: Installing Dependencies (Python 3.8)"

log_info "Installing from requirements_jetson.txt..."

if [ -f "requirements_jetson.txt" ]; then
    pip install -r requirements_jetson.txt
else
    log_warn "requirements_jetson.txt not found, installing manually..."
    pip install numpy==1.21.6 scipy==1.7.3 opencv-python==4.6.0.66
    pip install PyQt5==5.15.7
    pip install pyserial==3.5 pyserial-asyncio==0.4.0
    pip install pyrealsense2==2.50.0
    pip install psutil==5.9.4
fi

log_info "Phase 4 complete ✓"

# ============================================================
# PHASE 5: udev Rules & Final Setup
# ============================================================

log_header "PHASE 5/5: udev Rules & Final Configuration"

log_info "Setting up udev rules for ELM327/CAN adapters..."
sudo tee /etc/udev/rules.d/50-elm327.rules > /dev/null << 'EOF'
# Prolific PL2303 (common USB-serial adapters)
SUBSYSTEMS=="usb", ATTRS{idVendor}=="067b", ATTRS{idProduct}=="2303", \
    MODE="0666", GROUP="dialout"

# CH340/CH341 (popular on AliExpress adapters)
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", \
    MODE="0666", GROUP="dialout"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger

log_info "Adding ubuntu user to dialout group..."
sudo usermod -a -G dialout ubuntu
log_warn "NOTE: You must logout and login again for group changes to take effect!"

log_info "Phase 5 complete ✓"

# ============================================================
# VERIFICATION
# ============================================================

log_header "Verification & Testing"

log_info "Python version:"
python --version

log_info "PyTorch installation:"
python -c "import torch; print(f'  ✓ PyTorch {torch.__version__}')"

log_info "Key dependencies:"
python -c "
try:
    import cv2; print(f'  ✓ OpenCV {cv2.__version__}')
except: print('  ✗ OpenCV failed')
try:
    import numpy; print(f'  ✓ NumPy {numpy.__version__}')
except: print('  ✗ NumPy failed')
try:
    from PyQt5.QtWidgets import QApplication; print(f'  ✓ PyQt5 installed')
except: print('  ✗ PyQt5 failed')
try:
    import serial; print(f'  ✓ PySerial installed')
except: print('  ✗ PySerial failed')
"

# ============================================================
# FINAL INSTRUCTIONS
# ============================================================

log_header "Installation Complete! ✓"

echo -e "${CYAN}Next Steps:${NC}"
echo "  1. Logout and login again (for group changes)"
echo "     logout"
echo "     ssh ubuntu@jetson.local"
echo ""
echo "  2. Activate virtual environment:"
echo "     source ~/visionpilot/bin/activate"
echo ""
echo "  3. Run system tests:"
echo "     python jetson_test.py"
echo ""
echo "  4. Launch GUI (if X11/display available):"
echo "     export DISPLAY=:0"
echo "     python gui.py"
echo ""
echo "  5. Or run headless (CLI only):"
echo "     python vp_runtime.py"
echo ""
echo -e "${CYAN}Documentation:${NC}"
echo "  - See: JETSON_QUICK_REFERENCE.md"
echo "  - See: START_HERE.md"
echo ""
log_info "Happy computing! 🚀"
    pip install psutil
    pip install jetson-stats
fi

log_info "Phase 4 complete ✓"

# ============================================================
# PHASE 5: Configuration & Testing
# ============================================================

log_header "PHASE 5/5: Configuration & Testing"

# Create required directories
log_info "Creating project directories..."
mkdir -p log_files detections data_analysis CAN_logs MLP_report

# Setup udev rules for ELM327
log_info "Setting up udev rules for ELM327..."
sudo tee /etc/udev/rules.d/50-elm327.rules > /dev/null <<EOF
# ELM327 OBD-II Adapter
SUBSYSTEM=="tty", ATTRS{idVendor}=="067b", ATTRS{idProduct}=="2303", SYMLINK+="elm327", MODE="0666"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="elm327", MODE="0666"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger

log_info "Udev rules installed ✓"

# Run tests
log_info "Running system tests..."
if [ -f "jetson_test.py" ]; then
    python3 jetson_test.py
else
    log_warn "jetson_test.py not found"
fi

log_info "Phase 5 complete ✓"

# ============================================================
# SUMMARY
# ============================================================

log_header "Installation Summary"

log_info "✓ System updated"
log_info "✓ Python 3.11 venv created at: $VENV_PATH"
log_info "✓ PyTorch ARM64 installed"
log_info "✓ All dependencies installed"
log_info "✓ Configuration complete"

echo ""
log_header "Next Steps"

echo -e "${GREEN}To activate the environment:${NC}"
echo "  source $VENV_PATH/bin/activate"

echo -e "\n${GREEN}To run VisionPilot GUI:${NC}"
echo "  export DISPLAY=:0"
echo "  python3 gui.py"

echo -e "\n${GREEN}Or use the launcher script:${NC}"
echo "  bash run_visionpilot.sh"

echo -e "\n${GREEN}To enable automatic startup:${NC}"
echo "  sudo systemctl enable visionpilot"
echo "  sudo systemctl start visionpilot"

echo ""
log_info "Installation completed successfully! 🎉"

