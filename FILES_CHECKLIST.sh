#!/bin/bash
# File: FILES_CHECKLIST.sh
#
# VisionPilot XR - Jetson Orin Nano - Complete File Checklist
# Run this to verify all files are in place
#
# Usage: bash FILES_CHECKLIST.sh

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║    VisionPilot XR - Jetson Orin Nano - Files Checklist        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "${RED}✗${NC} $1 (MISSING!)"
        return 1
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} $1/"
        return 0
    else
        echo -e "${RED}✗${NC} $1/ (MISSING!)"
        return 1
    fi
}

PASSED=0
FAILED=0

# ========================================================
# MODIFIED FILES
# ========================================================
echo ""
echo -e "${YELLOW}═══ MODIFIED FILES ═══${NC}"

if check_file "gui.py"; then ((PASSED++)); else ((FAILED++)); fi
if check_file "gpu_processing.py"; then ((PASSED++)); else ((FAILED++)); fi

# ========================================================
# NEW CONFIG MODULE
# ========================================================
echo ""
echo -e "${YELLOW}═══ NEW CONFIG MODULE ═══${NC}"

if check_dir "config"; then ((PASSED++)); else ((FAILED++)); fi
if check_file "config/__init__.py"; then ((PASSED++)); else ((FAILED++)); fi
if check_file "config/platform_config.py"; then ((PASSED++)); else ((FAILED++)); fi

# ========================================================
# NEW SCRIPTS
# ========================================================
echo ""
echo -e "${YELLOW}═══ NEW SCRIPTS ═══${NC}"

if check_file "jetson_test.py"; then ((PASSED++)); else ((FAILED++)); fi
if check_file "run_visionpilot.sh"; then ((PASSED++)); else ((FAILED++)); fi
if check_file "install_jetson.sh"; then ((PASSED++)); else ((FAILED++)); fi

# ========================================================
# NEW REQUIREMENTS
# ========================================================
echo ""
echo -e "${YELLOW}═══ NEW REQUIREMENTS ═══${NC}"

if check_file "requirements_jetson.txt"; then ((PASSED++)); else ((FAILED++)); fi

# ========================================================
# DOCUMENTATION
# ========================================================
echo ""
echo -e "${YELLOW}═══ DOCUMENTATION (SLOVAK) ═══${NC}"

if check_file "JETSON_INSTALLATION_GUIDE_SK.md"; then ((PASSED++)); else ((FAILED++)); fi
if check_file "JETSON_DEPLOYMENT_SUMMARY.md"; then ((PASSED++)); else ((FAILED++)); fi
if check_file "JETSON_QUICK_REFERENCE.md"; then ((PASSED++)); else ((FAILED++)); fi

echo ""
echo -e "${YELLOW}═══ DOCUMENTATION (ENGLISH) ═══${NC}"

if check_file "JETSON_SETUP_GUIDE.md"; then ((PASSED++)); else ((FAILED++)); fi
if check_file "JETSON_PATCHES.md"; then ((PASSED++)); else ((FAILED++)); fi

echo ""
echo -e "${YELLOW}═══ DOCUMENTATION (INDEX) ═══${NC}"

if check_file "README_JETSON.md"; then ((PASSED++)); else ((FAILED++)); fi
if check_file "JETSON_DEPLOYMENT_COMPLETE.md"; then ((PASSED++)); else ((FAILED++)); fi

# ========================================================
# SUMMARY
# ========================================================
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"

TOTAL=$((PASSED + FAILED))

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL FILES PRESENT (${PASSED}/${TOTAL})${NC}"
    echo "║                                                              ║"
    echo "║  Your VisionPilot XR project is ready for Jetson!           ║"
    EXIT_CODE=0
else
    echo -e "${RED}✗ SOME FILES MISSING (${PASSED}/${TOTAL})${NC}"
    echo "║                                                              ║"
    echo "║  Please check the files marked with ✗ above.                ║"
    EXIT_CODE=1
fi

echo "╚════════════════════════════════════════════════════════════════╝"

# ========================================================
# NEXT STEPS
# ========================================================

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}NEXT STEPS:${NC}"
    echo "1. Read: README_JETSON.md or JETSON_QUICK_REFERENCE.md"
    echo "2. On Jetson, run: bash install_jetson.sh"
    echo "3. Verify with: python3 jetson_test.py"
    echo "4. Run GUI: python3 gui.py"
    echo ""
    echo -e "${GREEN}Documentation:${NC}"
    echo "  • Quick Start: JETSON_QUICK_REFERENCE.md"
    echo "  • Full Guide (SK): JETSON_INSTALLATION_GUIDE_SK.md"
    echo "  • Full Guide (EN): JETSON_SETUP_GUIDE.md"
    echo "  • Code Changes: JETSON_PATCHES.md"
fi

exit $EXIT_CODE

