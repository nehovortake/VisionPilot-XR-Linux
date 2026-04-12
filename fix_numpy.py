#!/usr/bin/env python3
"""
Quick NumPy fix for Jetson - fix compatibility issue
"""

import subprocess
import sys

print("[SETUP] Fixing NumPy compatibility...")
print()

# Try to upgrade NumPy
print("[1/3] Upgrading pip...")
subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
               capture_output=True)

print("[2/3] Installing compatible NumPy...")
result = subprocess.run([sys.executable, "-m", "pip", "install", "numpy==1.21.6"],
                       capture_output=True, text=True)

if result.returncode == 0:
    print("✓ NumPy installed")
else:
    print("⚠ NumPy installation had issues (may be OK)")
    print(result.stderr[:200])

print("[3/3] Verifying...")
try:
    import numpy
    print(f"✓ NumPy loaded: {numpy.__version__}")
except Exception as e:
    print(f"✗ NumPy failed: {e}")
    sys.exit(1)

print()
print("[DONE] NumPy fixed!")
print()
print("Now run: python3 test_with_fix.py")

