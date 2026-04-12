# JETSON - Pull Code from GitHub and Run

## Najjednoduššie - Jeden Skript

Na Jetsone spusti:

```bash
bash ~/Desktop/VisionPilot-XR-Linux/jetson_pull_and_run.sh
```

Alebo skopíruj a spusti tento príkaz:

```bash
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1 && \
cd ~/Desktop/VisionPilot-XR-Linux && \
git pull origin main && \
python3 main.py
```

---

## Manuálne Kroky

### Krok 1: Klonuj GitHub repo (PRVÝ RÁZ IBA)

```bash
cd ~/Desktop
git clone https://github.com/nehovortake/VisionPilot-XR-Linux.git
cd VisionPilot-XR-Linux
```

### Krok 2: Pull najnovší kód (VŽDY)

```bash
cd ~/Desktop/VisionPilot-XR-Linux
git pull origin main
```

Vidíš:
```
remote: Enumerating objects: 5, done.
...
Updating abc1234..def5678
Fast-forward
 main.py        | 10 ++
 read_speed.py  | 25 ++
 2 files changed, 35 insertions(+)
```

### Krok 3: Inštaluj dependencies (AK TREBA)

```bash
pip install numpy==1.21.6
pip install pyserial
```

### Krok 4: Nastav LD_PRELOAD (VŽDY)

```bash
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1
```

### Krok 5: Spusti aplikáciu

```bash
python3 main.py
```

---

## Očakávaný Výstup

```
[MAIN] ============================================
[MAIN] VisionPilot XR - Headless Mode
[MAIN] Platform: Linux
[MAIN] Device: NVIDIA Jetson (Unknown)
[MAIN] Python: 3.8
[MAIN] ============================================

[MAIN] Initializing all components...
[MAIN] [OK] Camera initialized
[MAIN] [OK] Image processor initialized
[MLP] Loaded | classes=[10,20,30,...] | img=64
[MAIN] [OK] ELM327 reader started

[MAIN] ✓ All components ready!

Vehicle speed: 0 km/h | Detected sign: No | Read sign: -- km/h
Vehicle speed: 0 km/h | Detected sign: Yes | Read sign: 50 km/h
Vehicle speed: 45 km/h | Detected sign: Yes | Read sign: 60 km/h
```

---

## Ak Chceš Aby Bežalo Automaticky

Pridan do `~/.bashrc`:

```bash
echo 'export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1' >> ~/.bashrc
source ~/.bashrc
```

Teraz pokaždé keď si ssh-neš na Jetson, LD_PRELOAD bude nastavený automaticky.

---

## Sumár - Copy-Paste

```bash
# PRVÝ RÁZ:
cd ~/Desktop
git clone https://github.com/nehovortake/VisionPilot-XR-Linux.git

# VŽDY PRED SPUSTENÍM:
cd ~/Desktop/VisionPilot-XR-Linux
git pull origin main
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1
python3 main.py
```

---

**Spusti to teraz na Jetsone!** 🎯

