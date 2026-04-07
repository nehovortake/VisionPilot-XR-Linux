# Python 3.8 Conversion Guide

## Summary of Changes

This project has been converted from **Python 3.10+** syntax to **Python 3.8 compatible** syntax.

### What Changed?

#### 1. Type Hints (Python 3.10+ → Python 3.8)

**Before (Python 3.10+):**
```python
from typing import Dict

def get_data(key: str) -> dict[str, int] | None:
    pass

self._cache: dict[int, QPixmap] = {}
self._last_val: int | None = None
```

**After (Python 3.8):**
```python
from typing import Dict, Optional, Union

def get_data(key):
    # type: (str) -> Optional[Dict[str, int]]
    pass

self._cache: Dict[int, QPixmap] = {}
self._last_val: Optional[int] = None
```

#### 2. Files Modified

| File | Changes |
|------|---------|
| `gui.py` | ✓ Added `typing` imports, replaced `dict[...]` with `Dict[...]`, replaced `\|` with `Union`/`Optional` |
| `vp_runtime.py` | ✓ Replaced `float \| None` with `Optional[float]` |
| `red_nuling_preprocessing.py` | ✓ Replaced `str \| None` with `Optional[str]`, `dict` with `Dict` |
| `read_speed.py` | ✓ Replaced `int \| None` with `Optional[int]` |
| `qt_weather_detection.py` | ✓ Replaced `tuple[float, float, float]` with `Tuple[float, float, float]` |
| `qt_read_sign.py` | ✓ Replaced `int \| None` with `Optional[int]` |

#### 3. Dependencies Updated

**requirements_jetson.txt:**
- `numpy==1.21.6` (Python 3.8 compatible)
- `scipy==1.7.3` (Python 3.8 compatible)
- `opencv-python==4.6.0.66` (Python 3.8 compatible)
- `PyQt5==5.15.7` (Python 3.8 compatible)
- `torch==1.13.1` (Python 3.8 compatible, ARM64)
- `torchvision==0.14.1` (Python 3.8 compatible)
- `torchaudio==0.13.1` (Python 3.8 compatible)
- `pyserial==3.5` (Python 3.8 compatible)
- `psutil==5.9.4` (Python 3.8 compatible)

#### 4. Installation Scripts Updated

**install_jetson.sh:**
- Changed from `python3.11` to `python3.8`
- Updated PyTorch version to `1.13.1` (Python 3.8 compatible)
- Fixed virtual environment creation
- Added Python 3.8 detection

---

## Testing

### Local Test (Windows/Linux)
```bash
python3.8 -m py_compile gui.py
python3.8 -m py_compile read_speed.py
python3.8 -m py_compile qt_read_sign.py
```

### Jetson Test
```bash
ssh ubuntu@jetson.local
source ~/visionpilot/bin/activate
python jetson_test.py
python gui.py
```

---

## Compatibility Matrix

| Component | Python 3.8 | Jetson | ARM64 | Status |
|-----------|-----------|--------|-------|--------|
| PyTorch | 1.13.1 | ✅ Yes | ✅ Yes | ✅ Tested |
| OpenCV | 4.6.0 | ✅ Yes | ✅ Yes | ✅ Working |
| PyQt5 | 5.15.7 | ✅ Yes | ✅ Yes | ✅ Working |
| NumPy | 1.21.6 | ✅ Yes | ✅ Yes | ✅ Working |
| SciPy | 1.7.3 | ✅ Yes | ✅ Yes | ✅ Working |

---

## Known Limitations

1. **No `from __future__ import annotations`** in Python 3.8
   - Type hints use comment style instead: `# type: (str) -> int`

2. **No walrus operator `:=`** (Python 3.8)
   - Use traditional assignment instead

3. **No `match/case`** (Python 3.8)
   - Code doesn't use these (only comments contain "match")

---

## Rollback Instructions

If you need to go back to Python 3.10+ syntax:

```bash
# Find all type hint comments
grep -r "# type:" *.py

# Replace with modern syntax (manual or with script)
```

---

## Future Upgrades

When moving to Python 3.9+:
1. Use `from __future__ import annotations` at top of files
2. Replace `Optional[T]` with `T | None`
3. Replace `Union[T1, T2]` with `T1 | T2`
4. Replace `Dict[K, V]` with `dict[K, V]`
5. Use `match/case` if needed

---

## Support

For issues:
1. Run `python jetson_test.py` to diagnose
2. Check `JETSON_QUICK_REFERENCE.md`
3. See `JETSON_INSTALLATION_GUIDE_SK.md` for troubleshooting

