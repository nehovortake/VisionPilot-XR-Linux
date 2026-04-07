#!/bin/bash

# VisionPilot XR - JETSON ORIN NANO - FULL INSTALLATION SCRIPT
#
# Táto šanóna automaticky inštaluje VisionPilot na Jetson Orin Nano
#
# Predpoklady:
#   - JetPack 6.0+ nainštalovaný
#   - SSH prístup na Jetson
#   - Internet pripojenie
#
# Použitie:
#   ssh ubuntu@jetson.local
#   bash install_jetson.sh
#
# OR na Windows (PowerShell):
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
NC='\033[0m'

# Logging
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_header() { echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"; echo -e "${BLUE}║  $1${NC}"; echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"; }

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

log_header "VisionPilot XR - Jetson Installation"

# ============================================================
# PHASE 1: System Update
# ============================================================

log_header "PHASE 1/5: System Update"

log_info "Updating package lists..."
sudo apt update

log_info "Upgrading packages..."
sudo apt upgrade -y

log_info "Installing development tools..."
sudo apt install -y \
    build-essential \
    cmake \
    git \
    python3.11-dev \
    python3.11-venv \
    libpython3.11-dev \
    udev

log_info "Phase 1 complete ✓"

# ============================================================
# PHASE 2: Virtual Environment
# ============================================================

log_header "PHASE 2/5: Python Virtual Environment"

if [ -d "$VENV_PATH" ]; then
    log_warn "Virtual environment already exists at $VENV_PATH"
    read -p "Remove and recreate? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_PATH"
        log_info "Creating new virtual environment..."
        python3.11 -m venv "$VENV_PATH"
    fi
else
    log_info "Creating new virtual environment..."
    python3.11 -m venv "$VENV_PATH"
fi

# Activate venv
source "$VENV_PATH/bin/activate"
log_info "Virtual environment activated ✓"

# Upgrade pip
log_info "Upgrading pip..."
pip install --upgrade pip setuptools wheel

log_info "Phase 2 complete ✓"

# ============================================================
# PHASE 3: PyTorch (ARM64)
# ============================================================

log_header "PHASE 3/5: PyTorch ARM64 (CRITICAL!)"

log_warn "This step is CRITICAL - PyTorch ARM64 wheels must be installed"
log_info "Installing PyTorch 2.1 with CUDA 12.1 support..."

pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Verify PyTorch
log_info "Verifying PyTorch installation..."
python3 -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA device: {torch.cuda.get_device_name(0)}')
    print(f'CUDA version: {torch.version.cuda}')
"

log_info "Phase 3 complete ✓"

# ============================================================
# PHASE 4: Dependencies
# ============================================================

log_header "PHASE 4/5: Installing Dependencies"

log_info "Installing from requirements_jetson.txt..."

# Check if requirements file exists
if [ -f "requirements_jetson.txt" ]; then
    pip install -r requirements_jetson.txt
else
    log_warn "requirements_jetson.txt not found, installing manually..."
    pip install numpy scipy opencv-python
    pip install PyQt5
    pip install pyserial
    pip install pyrealsense2
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

