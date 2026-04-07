#!/usr/bin/env python3
"""
VisionPilot XR - Jetson Orin Nano System Test Script

Run this FIRST on your Jetson to verify all dependencies are correctly installed.

Usage:
    python3 jetson_test.py

Expected Output:
    ✓ All tests pass with green checkmarks
"""

import sys
import os
import platform

def print_header(text):
    """Print section header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)

def test_result(name, passed, details=""):
    """Print test result."""
    symbol = "✓" if passed else "✗"
    status = "\033[92m✓ PASS\033[0m" if passed else "\033[91m✗ FAIL\033[0m"
    print(f"  [{symbol}] {name:40} {status}")
    if details:
        print(f"      └─ {details}")

def test_system_info():
    """Test 1: System Information."""
    print_header("1. SYSTEM INFORMATION")

    print(f"  OS: {platform.system()} {platform.release()}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Executable: {sys.executable}")

    # Jetson detection
    is_jetson = os.path.exists("/etc/nv_tegra_release")
    test_result("Jetson Detection", is_jetson,
                "NVIDIA Jetson" if is_jetson else "Desktop Linux/Windows/Mac")

    if is_jetson:
        try:
            with open("/etc/nv_tegra_release") as f:
                content = f.read()
                for line in content.split('\n'):
                    if 'JETSON' in line.upper():
                        print(f"      └─ {line.strip()}")
                        break
        except Exception:
            pass

def test_pytorch():
    """Test 2: PyTorch & CUDA."""
    print_header("2. PYTORCH & CUDA")

    try:
        import torch
        test_result("PyTorch Import", True, f"Version: {torch.__version__}")
    except ImportError as e:
        test_result("PyTorch Import", False, str(e))
        return False

    # CUDA availability
    try:
        cuda_available = torch.cuda.is_available()
        test_result("CUDA Available", cuda_available)

        if cuda_available:
            try:
                device_name = torch.cuda.get_device_name(0)
                test_result("CUDA Device Name", True, device_name)
            except Exception as e:
                test_result("CUDA Device Name", False, str(e))

            try:
                cuda_version = torch.version.cuda
                test_result("CUDA Version", True, f"CUDA {cuda_version}")
            except Exception as e:
                test_result("CUDA Version", False, str(e))

            try:
                gpu_mem = torch.cuda.get_device_properties(0).total_memory
                gpu_mem_gb = gpu_mem / (1024**3)
                test_result("GPU Memory", True, f"{gpu_mem_gb:.1f} GB")
            except Exception as e:
                test_result("GPU Memory", False, str(e))
    except Exception as e:
        test_result("CUDA Check", False, str(e))
        return False

    return True

def test_opencv():
    """Test 3: OpenCV."""
    print_header("3. OPENCV")

    try:
        import cv2
        test_result("OpenCV Import", True, f"Version: {cv2.__version__}")
    except ImportError as e:
        test_result("OpenCV Import", False, str(e))
        return False

    try:
        # Check CUDA support in OpenCV
        cuda_compiled = cv2.cuda.getCudaEnabledDeviceCount() >= 0
        if cuda_compiled:
            device_count = cv2.cuda.getCudaEnabledDeviceCount()
            test_result("OpenCV CUDA", True, f"{device_count} CUDA device(s)")
        else:
            test_result("OpenCV CUDA", False, "OpenCV not compiled with CUDA (CPU only)")
    except Exception as e:
        test_result("OpenCV CUDA", False, str(e))

    return True

def test_realsense():
    """Test 4: RealSense."""
    print_header("4. REALSENSE CAMERA")

    try:
        import pyrealsense2 as rs
        test_result("RealSense Import", True, "pyrealsense2 available")
    except ImportError as e:
        test_result("RealSense Import", False, str(e))
        return False

    try:
        ctx = rs.context()
        devices = ctx.query_devices()
        device_count = devices.size()

        if device_count > 0:
            test_result("RealSense Devices", True, f"{device_count} device(s) connected")
            for i in range(device_count):
                dev = devices[i]
                name = dev.get_info(rs.camera_info.name)
                serial = dev.get_info(rs.camera_info.serial_number)
                print(f"      └─ [{i}] {name} (S/N: {serial})")
        else:
            test_result("RealSense Devices", False, "No cameras connected")
    except Exception as e:
        test_result("RealSense Devices", False, str(e))
        return False

    return True

def test_pyserial():
    """Test 5: PySerial & ELM327."""
    print_header("5. PYSERIAL & ELM327")

    try:
        import serial
        test_result("PySerial Import", True, f"Version: {serial.__version__}")
    except ImportError as e:
        test_result("PySerial Import", False, str(e))
        return False

    try:
        from elm327_can_speed import ELM327SpeedReader
        test_result("ELM327 Module", True, "elm327_can_speed.py imported")
    except ImportError as e:
        test_result("ELM327 Module", False, str(e))

    # Check available serial ports
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())

        if ports:
            test_result("Serial Ports", True, f"{len(ports)} port(s) available")
            for port in ports:
                print(f"      └─ {port.device}: {port.description}")
        else:
            test_result("Serial Ports", False, "No serial ports detected")
            print("      └─ Connect OBD-II adapter to USB port")
    except Exception as e:
        test_result("Serial Ports", False, str(e))

    return True

def test_qt():
    """Test 6: PyQt5 GUI."""
    print_header("6. PYQT5 GUI")

    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import QT_VERSION_STR
        test_result("PyQt5 Import", True, f"Qt Version: {QT_VERSION_STR}")
    except ImportError as e:
        test_result("PyQt5 Import", False, str(e))
        return False

    return True

def test_numpy():
    """Test 7: NumPy & SciPy."""
    print_header("7. NUMPY & SCIPY")

    try:
        import numpy as np
        test_result("NumPy Import", True, f"Version: {np.__version__}")
    except ImportError as e:
        test_result("NumPy Import", False, str(e))
        return False

    try:
        import scipy
        test_result("SciPy Import", True, f"Version: {scipy.__version__}")
    except ImportError as e:
        test_result("SciPy Import", False, str(e))

    return True

def test_psutil():
    """Test 8: System Monitoring."""
    print_header("8. SYSTEM MONITORING")

    try:
        import psutil
        test_result("PSUtil Import", True, f"Version: {psutil.__version__}")

        # Get system stats
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        test_result("CPU Usage", True, f"{cpu:.1f}%")
        test_result("Memory Usage", True, f"{mem.percent:.1f}% ({mem.used / (1024**3):.1f} GB / {mem.total / (1024**3):.1f} GB)")
        test_result("Disk Usage", True, f"{disk.percent:.1f}% ({disk.used / (1024**3):.1f} GB / {disk.total / (1024**3):.1f} GB)")
    except ImportError as e:
        test_result("PSUtil Import", False, str(e))
    except Exception as e:
        test_result("System Stats", False, str(e))

    return True

def test_custom_modules():
    """Test 9: Custom VisionPilot Modules."""
    print_header("9. CUSTOM MODULES")

    # Try importing custom modules
    modules = [
        ("image_processing", "ImageProcessor"),
        ("gpu_processing", "GPUProcessor"),
        ("fast_ellipse_detection", None),
        ("red_nuling_preprocessing", None),
    ]

    all_ok = True
    for module_name, class_name in modules:
        try:
            mod = __import__(module_name)
            if class_name:
                getattr(mod, class_name)
                test_result(f"{module_name}.{class_name}", True)
            else:
                test_result(module_name, True)
        except ImportError as e:
            test_result(module_name, False, str(e))
            all_ok = False
        except Exception as e:
            test_result(module_name, False, str(e))
            all_ok = False

    return all_ok

def test_platform_config():
    """Test 10: Platform Configuration."""
    print_header("10. PLATFORM CONFIGURATION")

    try:
        from config.platform_config import (
            IS_JETSON, IS_WINDOWS, IS_LINUX,
            get_serial_port, get_asset_path,
            SYSTEM_NAME
        )

        test_result("platform_config.py", True)
        print(f"      └─ System: {SYSTEM_NAME}")
        print(f"      └─ Is Jetson: {IS_JETSON}")
        print(f"      └─ Serial Port: {get_serial_port()}")

        return True
    except ImportError as e:
        test_result("platform_config.py", False, str(e))
        return False

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  VISIONPILOT XR - JETSON ORIN NANO SYSTEM TEST")
    print("="*60)

    results = {
        "System Info": test_system_info(),
        "PyTorch": test_pytorch(),
        "OpenCV": test_opencv(),
        "RealSense": test_realsense(),
        "PySerial": test_pyserial(),
        "PyQt5": test_qt(),
        "NumPy": test_numpy(),
        "PSUtil": test_psutil(),
        "Custom Modules": test_custom_modules(),
        "Platform Config": test_platform_config(),
    }

    # Summary
    print_header("TEST SUMMARY")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    for name, result in results.items():
        status = "\033[92m✓\033[0m" if result else "\033[91m✗\033[0m"
        print(f"  [{status}] {name}")

    print(f"\n  Total: {passed}/{total} tests passed")

    if failed == 0:
        print("\n  \033[92m🎉 ALL TESTS PASSED - READY FOR DEPLOYMENT!\033[0m\n")
        return 0
    else:
        print(f"\n  \033[91m⚠️  {failed} test(s) failed - see details above\033[0m\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())

