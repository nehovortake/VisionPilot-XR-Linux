import cv2
import numpy as np
import os
import random
import sys
import time

# ============================================================
# CIEĽOVÝ PRIEČINOK
# ============================================================

OUTPUT_PATH = r"C:\Users\Minko\Desktop\DP\VisionPilot-XR Win\Py dataset"

# ============================================================
# TRIEDY
# ============================================================

speeds = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 130]

# ============================================================
# FONTY
# ============================================================

fonts = [
    cv2.FONT_HERSHEY_SIMPLEX,
    cv2.FONT_HERSHEY_DUPLEX,
    cv2.FONT_HERSHEY_COMPLEX,
    cv2.FONT_HERSHEY_TRIPLEX,
    cv2.FONT_HERSHEY_COMPLEX_SMALL,
    cv2.FONT_HERSHEY_PLAIN,
]

# ============================================================
# PARAMETRE
# ============================================================

IMG_SIZE = 64
IMAGES_PER_SPEED = 5000
MARGIN = 4

N_NORMAL  = 3500
N_MILD    = 1000
N_STRONG  = 375
N_EXTREME = 125

# ============================================================
# CIEĽOVÁ VÝŠKA ČÍSLIC
# ============================================================

TARGET_H = IMG_SIZE - 2 * MARGIN


def compute_scale(text, font, thickness):
    probe = 10.0
    (tw, th), _ = cv2.getTextSize(text, font, probe, thickness)
    s = probe * TARGET_H / th
    (tw2, _), _ = cv2.getTextSize(text, font, s, thickness)
    max_w = IMG_SIZE - 2 * MARGIN
    if tw2 > max_w:
        s = s * max_w / tw2
    return s


# ============================================================
# TIMER
# ============================================================

normal_time = 0.0
mild_time = 0.0
strong_time = 0.0
extreme_time = 0.0

# ============================================================
# DEFORMÁCIE
# ============================================================

def mild_deformation(img):
    angle = random.uniform(-7, 7)
    M = cv2.getRotationMatrix2D((IMG_SIZE / 2, IMG_SIZE / 2), angle, 1)
    img = cv2.warpAffine(img, M, (IMG_SIZE, IMG_SIZE), borderValue=255)
    if random.random() < 0.4:
        img = cv2.GaussianBlur(img, (3, 3), 0)
    return img


def strong_deformation(img):
    angle = random.uniform(-15, 15)
    M = cv2.getRotationMatrix2D(
        (IMG_SIZE / 2, IMG_SIZE / 2), angle, random.uniform(0.9, 1.1)
    )
    img = cv2.warpAffine(img, M, (IMG_SIZE, IMG_SIZE), borderValue=255)
    shift = 6
    pts1 = np.float32([[0, 0], [IMG_SIZE, 0], [0, IMG_SIZE], [IMG_SIZE, IMG_SIZE]])
    pts2 = np.float32([
        [random.randint(0, shift), random.randint(0, shift)],
        [IMG_SIZE - random.randint(0, shift), random.randint(0, shift)],
        [random.randint(0, shift), IMG_SIZE - random.randint(0, shift)],
        [IMG_SIZE - random.randint(0, shift), IMG_SIZE - random.randint(0, shift)],
    ])
    M = cv2.getPerspectiveTransform(pts1, pts2)
    img = cv2.warpPerspective(img, M, (IMG_SIZE, IMG_SIZE), borderValue=255)
    return img


def extreme_deformation(img):
    img = strong_deformation(img)
    x = random.randint(0, IMG_SIZE - 10)
    y = random.randint(0, IMG_SIZE - 10)
    cv2.rectangle(img, (x, y),
                  (x + random.randint(5, 15), y + random.randint(5, 15)), 255, -1)
    img = cv2.GaussianBlur(img, (5, 5), 0)
    return img


# ============================================================
# PRE-COMPUTE SCALE
# ============================================================

THICK_OPTIONS = [2, 3]
scale_cache = {}
for sp in speeds:
    for fi, fo in enumerate(fonts):
        for th in THICK_OPTIONS:
            scale_cache[(sp, fi, th)] = compute_scale(str(sp), fo, th)

# ============================================================
# PROGRESS
# ============================================================

total_images = len(speeds) * IMAGES_PER_SPEED
generated = 0

print("Generovanie datasetu")
print(f"Celkom obrazkov: {total_images}")
print(f"Na rychlost: {IMAGES_PER_SPEED}  "
      f"(normal={N_NORMAL}, mild={N_MILD}, strong={N_STRONG}, extreme={N_EXTREME})")
print(f"Velkost: {IMG_SIZE}x{IMG_SIZE}, okraj: {MARGIN} px, vyska cislic: {TARGET_H} px")

start_total = time.perf_counter()

# ============================================================
# GENEROVANIE
# ============================================================

for speed in speeds:
    print(f"\nRychlost: {speed}")

    speed_dir = os.path.join(OUTPUT_PATH, str(speed))
    dirs = {}
    for cat in ("normal", "mild", "strong", "extreme"):
        d = os.path.join(speed_dir, cat)
        os.makedirs(d, exist_ok=True)
        dirs[cat] = d

    imgs_per_font = IMAGES_PER_SPEED // len(fonts)
    leftover = IMAGES_PER_SPEED - imgs_per_font * len(fonts)

    cat_list = (["normal"] * N_NORMAL
                + ["mild"] * N_MILD
                + ["strong"] * N_STRONG
                + ["extreme"] * N_EXTREME)
    random.shuffle(cat_list)

    img_idx = 0
    for font_id, font in enumerate(fonts):
        count = imgs_per_font + (1 if font_id < leftover else 0)
        print(f"  Font {font_id} ({count} obrazkov)")

        for i in range(count):
            text = str(speed)
            thickness = random.choice([2, 2, 2, 3])
            scale = scale_cache[(speed, font_id, thickness)]

            img = np.ones((IMG_SIZE, IMG_SIZE), dtype=np.uint8) * 255

            (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
            x = (IMG_SIZE - tw) // 2
            y = (IMG_SIZE + th) // 2

            cv2.putText(img, text, (x, y), font, scale, 0, thickness, cv2.LINE_AA)

            cat = cat_list[img_idx]
            img_idx += 1

            t0 = time.perf_counter()
            if cat == "mild":
                img = mild_deformation(img)
                mild_time += time.perf_counter() - t0
            elif cat == "strong":
                img = strong_deformation(img)
                strong_time += time.perf_counter() - t0
            elif cat == "extreme":
                img = extreme_deformation(img)
                extreme_time += time.perf_counter() - t0

            filename = f"{speed}_f{font_id}_{i}.png"
            cv2.imwrite(os.path.join(dirs[cat], filename), img)

            generated += 1
            if generated % 500 == 0:
                percent = generated / total_images * 100
                sys.stdout.write(f"\rProgress {generated}/{total_images} ({percent:.1f}%)")
                sys.stdout.flush()

# ============================================================
# VYSLEDOK
# ============================================================

total_time = time.perf_counter() - start_total

print(f"\n\nHotovo!\n")
print(f"Celkovy cas: {total_time:.2f} s")
print(f"\nCasy deformacii:")
print(f"  mild   : {mild_time:.4f} s")
print(f"  strong : {strong_time:.4f} s")
print(f"  extreme: {extreme_time:.4f} s")
print(f"\nDataset ulozeny do: {OUTPUT_PATH}")
