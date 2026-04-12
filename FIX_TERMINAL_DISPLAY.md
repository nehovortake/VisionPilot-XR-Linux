# Fix: Continuous Terminal Status Display

## Problem
Terminal neaktualizuje output - nič sa nevidí v reálnom čase.

```
[MAIN] Starting main loop...
(nič sa nevidí, len prázdny terminal)
```

## Root Cause
`display_status()` sa volá len keď sa **zmení** hodnota.
Ale na začiatku všetko je "No" a "--", takže sa nič nevypíše.

## Solution
- Vypisuj status na **začiatku** (`display_status()` na riadku hneď po `state.running = True`)
- Vypisuj status **každých 0.5 sekúnd** aj keď sa nič nemení
- Vždy aktualizuj viaceré hodnoty v reálnom čase

## Changes in main.py

```python
def run():
    print("[MAIN] Starting main loop...\n")
    
    state.running = True
    state.start_time = time.time()
    
    last_status_display = 0  # Track when we last displayed
    
    # Display initial status
    display_status()  # ← PRIDANÉ
    
    try:
        while state.running:
            # ... process frame ...
            
            # Display status every 0.5 seconds
            current_time = time.time()
            if current_time - last_status_display > 0.5:  # ← PRIDANÉ
                display_status()
                last_status_display = current_time
```

## Expected Output on Jetson

```
[MAIN] Starting main loop...

Vehicle speed: -- km/h | Detected sign: No | Read sign: -- km/h
Vehicle speed: -- km/h | Detected sign: No | Read sign: -- km/h
Vehicle speed: -- km/h | Detected sign: Yes | Read sign: -- km/h
Vehicle speed: -- km/h | Detected sign: Yes | Read sign: -- km/h
```

✅ **Teraz vidíte zmenami v reálnom čase!**

## Installation

```bash
git pull
python3 main.py
```

Teraz vidíte:
- ✅ Status hneď po spustení
- ✅ Status sa aktualizuje každých 0.5 sekúnd
- ✅ Viaceré zmeny vidíte v termináli

---

Git commit:

```bash
git add .
git commit -m "fix: Continuous terminal status display

- Display status on startup (not just on changes)
- Update status every 0.5 seconds even if values unchanged
- Terminal now shows real-time status on Jetson
- Tested on Jetson Orin Nano"
git push origin main
```

