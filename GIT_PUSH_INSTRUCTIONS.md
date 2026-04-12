# GIT PUSH - Ako poslať kód na GitHub

## Najjednoduššie - Copy-Paste Príkazy

Na príkazovom riadku (Terminal/CMD/PowerShell):

```bash
cd C:\Users\Minko\Desktop\DP\VisionPilot-XR\ Linux

git add .

git commit -m "fix: Use working Windows read_speed.py for Jetson"

git push origin main
```

---

## Alebo spusti skript

```bash
bash push_to_git.sh
```

---

## Čo sa stane

1. **git add .** - Pridá všetky zmeny
2. **git commit** - Zapíše zmeny s popisom
3. **git push** - Pošle na GitHub

---

## Keď je hotovo

Vidíš v termináli:
```
✓ Push complete!

Verify on GitHub: https://github.com/nehovortake/VisionPilot-XR-Linux
```

---

## Ak je problém s autentifikáciou

GitHub si bude žiadať token. Skopíruj si ho z:
- https://github.com/settings/tokens

A vlož ho ako heslo keď sa pýta.

---

**Spusti teraz na Windows PowerShell/CMD!** 🎯

