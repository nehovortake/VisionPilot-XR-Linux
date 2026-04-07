#!/bin/bash

# VisionPilot XR - Jetson Orin Nano Launcher Script
#
# This script sets up the environment and runs VisionPilot GUI on Jetson
#
# Usage:
#   ./run_visionpilot.sh
#   ./run_visionpilot.sh background   # Run in background

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$HOME/visionpilot"
RUN_MODE="${1:-foreground}"

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  VisionPilot XR - Jetson Launcher     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}✗ Virtual environment not found: $VENV_PATH${NC}"
    echo -e "${YELLOW}Please run setup first:${NC}"
    echo "  python3.11 -m venv $VENV_PATH"
    echo "  source $VENV_PATH/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

echo -e "${GREEN}✓ Virtual environment found${NC}"

# Activate venv
source "$VENV_PATH/bin/activate"
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Check Python
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ Python ${PYTHON_VERSION}${NC}"

# Check CUDA
CUDA_CHECK=$(python3 -c "import torch; print('OK' if torch.cuda.is_available() else 'FAIL')" 2>/dev/null || echo "FAIL")
if [ "$CUDA_CHECK" = "OK" ]; then
    echo -e "${GREEN}✓ CUDA available${NC}"
else
    echo -e "${YELLOW}⚠ CUDA not available (CPU mode)${NC}"
fi

# Check camera
CAMERA_CHECK=$(python3 -c "import pyrealsense2; ctx = pyrealsense2.context(); devices = ctx.query_devices(); print(devices.size())" 2>/dev/null || echo "0")
echo -e "${GREEN}✓ RealSense cameras detected: ${CAMERA_CHECK}${NC}"

# Check serial port
if [ -c "/dev/ttyUSB0" ]; then
    echo -e "${GREEN}✓ Serial port /dev/ttyUSB0 available${NC}"
else
    echo -e "${YELLOW}⚠ Serial port /dev/ttyUSB0 not found (ELM327 not connected)${NC}"
fi

# Set DISPLAY if not set
if [ -z "$DISPLAY" ]; then
    echo -e "${YELLOW}Setting DISPLAY=:0${NC}"
    export DISPLAY=:0
fi

# Enable jetson_clocks for performance (optional)
if command -v jetson_clocks &> /dev/null; then
    echo -e "${YELLOW}Checking jetson_clocks...${NC}"
    if ! sudo jetson_clocks 2>/dev/null; then
        echo -e "${YELLOW}⚠ jetson_clocks failed (not critical)${NC}"
    else
        echo -e "${GREEN}✓ jetson_clocks enabled${NC}"
    fi
fi

# Final checks
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Environment Ready - Starting GUI     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""

# Run application
if [ "$RUN_MODE" = "background" ]; then
    echo -e "${YELLOW}Starting in background mode...${NC}"
    nohup python3 "$SCRIPT_DIR/gui.py" > /tmp/visionpilot.log 2>&1 &
    PID=$!
    echo -e "${GREEN}✓ VisionPilot running (PID: $PID)${NC}"
    echo -e "${YELLOW}Check logs: tail -f /tmp/visionpilot.log${NC}"
else
    echo -e "${YELLOW}Starting in foreground mode...${NC}"
    echo -e "${YELLOW}Press Ctrl+C to exit${NC}"
    echo ""
    python3 "$SCRIPT_DIR/gui.py"
fi

