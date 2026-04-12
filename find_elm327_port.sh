#!/bin/bash
# Detect ELM327 serial port on Jetson

echo "Searching for ELM327 serial ports..."
echo ""

# List all serial ports
echo "Available serial ports:"
ls -la /dev/ttyUSB* 2>/dev/null || echo "  No /dev/ttyUSB* found"
ls -la /dev/ttyACM* 2>/dev/null || echo "  No /dev/ttyACM* found"
ls -la /dev/ttyS* 2>/dev/null || echo "  No /dev/ttyS* found"

echo ""
echo "Checking USB devices:"
lsusb | grep -i serial || echo "  No serial devices found in lsusb"

echo ""
echo "Checking dmesg for recent USB connections:"
dmesg | tail -20 | grep -i "usb\|serial" || echo "  No recent USB/serial messages"

echo ""
echo "All /dev entries:"
ls -1 /dev/tty* 2>/dev/null | head -20

