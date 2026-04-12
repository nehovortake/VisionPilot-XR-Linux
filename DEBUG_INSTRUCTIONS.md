# DEBUG MLP - Zistenie Problému

## Co Som Urobil

Pridal som **detailný debug výstup** do `predict_from_crop()` aby sme videli presne kde sa predikcie zamietajú.

## Na Jetsone - Spusti:

```bash
cd ~/Desktop/VisionPilot-XR-Linux
git pull origin main
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1
python3 main.py
```

## Debug Output - Co Vidíš v Termináli:

Keď kod vidí značku, vidíš v termináli:

```
[MLP-DEBUG] Variant 'default': prob=0.850, margin=0.123, label=50
[MLP-DEBUG] Variant 'three_pad': prob=0.920, margin=0.456, label=50
[MLP-DEBUG] Best: label=50, prob=0.920, margin=0.456
[MLP-DEBUG] REJECTED: prob=0.920 < softmax_threshold=0.9
```

Alebo:

```
[MLP-DEBUG] Variant 'default': prob=0.750, margin=0.050, label=110
[MLP-DEBUG] Best: label=110, prob=0.750, margin=0.050
[MLP-DEBUG] REJECTED: prob=0.750 < softmax_threshold=0.9
```

Alebo:

```
[MLP-DEBUG] Best: label=50, prob=0.95, margin=0.45
[MLP-DEBUG] REJECTED: margin=0.45 < margin_threshold=0.35
```

Alebo:

```
[MLP-DEBUG] ACCEPTED: speed=50 km/h (votes=4)
```

---

## Pošli Mi Output

Keď spustíš `python3 main.py` a vidíš značku, **pošli mi všetky riadky s `[MLP-DEBUG]`** 

Podľa debug výstupu zistím čo je problém a opravím to.

---

## Spusti Teraz a Pošli Output! 🎯

```bash
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1 && \
cd ~/Desktop/VisionPilot-XR-Linux && \
git pull origin main && \
python3 main.py
```

**Keď vidíš značku, pošli mi debug riadky!**

