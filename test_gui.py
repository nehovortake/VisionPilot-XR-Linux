#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick test to verify detection flags work"""

import sys
import time

# Test imports
try:
    from image_processing import ImageProcessor
    print("[TEST] ✓ ImageProcessor imported")
except Exception as e:
    print(f"[TEST] ✗ Failed to import ImageProcessor: {e}")
    sys.exit(1)

# Create processor
processor = ImageProcessor()
print(f"[TEST] ✓ ImageProcessor created")

# Check attributes
if hasattr(processor, 'sign_detected_this_frame'):
    print(f"[TEST] ✓ sign_detected_this_frame attribute exists: {processor.sign_detected_this_frame}")
else:
    print(f"[TEST] ✗ sign_detected_this_frame attribute NOT found")
    sys.exit(1)

# Check process method
if hasattr(processor, 'process'):
    print(f"[TEST] ✓ process method exists")
else:
    print(f"[TEST] ✗ process method NOT found")
    sys.exit(1)

print("\n[TEST] All checks passed!")

