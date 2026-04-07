import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset, random_split

import numpy as np
import cv2
from pathlib import Path
import random
import csv
import os
import sys
import subprocess
from datetime import datetime
import time

import matplotlib.pyplot as plt


# ======================================================
# CONFIG
# ======================================================

DATASET_ROOT = Path(r"C:\Users\Minko\Desktop\DP\VisionPilot-XR Win\dataset_mlp")
MODEL_PATH = DATASET_ROOT / "mlp_speed_model.pt"

PROJECT_ROOT = DATASET_ROOT.parent
REPORT_DIR = PROJECT_ROOT / "MLP_report" / "02_training_results"

SPEED_CLASSES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 130]

IMG_SIZE = 64
INPUT_DIM = IMG_SIZE * IMG_SIZE  # 4096

BATCH_SIZE = 256          # 🔥 GPU zvládne vyššie batchy (na CPU nechaj 64)
EPOCHS = 30
LR = 0.0005
WEIGHT_DECAY = 1e-4

THREE_DIGIT = {100, 110, 130}

# GPU / performance
USE_AMP = True            # mixed precision (iba na CUDA)
NUM_WORKERS = 0           # na Windows 0 je najbezpečnejšie (vyhne sa multiprocessing deadlockom)
PIN_MEMORY = True         # pomáha pri CUDA


# ======================================================
# PREPROCESS
# ======================================================

def preprocess(img_bgr, speed):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    h, w = gray.shape
    cx, cy = w // 2, h // 2

    if speed in THREE_DIGIT:
        inner_scale = 1.0
        focus_scale = 1.0
        crop_mode = "pad"
    else:
        inner_scale = 0.75
        focus_scale = 0.90
        crop_mode = "crop"

    r = int(inner_scale * 0.5 * min(w, h))
    mask = np.zeros_like(gray, np.uint8)
    cv2.circle(mask, (cx, cy), r, 255, -1)
    inner = cv2.bitwise_and(gray, gray, mask=mask)

    if crop_mode == "pad":
        s0 = max(h, w)
        canvas = np.zeros((s0, s0), dtype=inner.dtype)
        y_off = (s0 - h) // 2
        x_off = (s0 - w) // 2
        canvas[y_off:y_off + h, x_off:x_off + w] = inner
        inner = canvas
        s0 = s0
    else:
        s0 = min(h, w)

    s = int(s0 * focus_scale)
    s = max(8, min(s, s0))

    x0 = max(0, cx - s // 2)
    y0 = max(0, cy - s // 2)
    x0 = min(x0, inner.shape[1] - s)
    y0 = min(y0, inner.shape[0] - s)

    inner = inner[y0:y0 + s, x0:x0 + s]
    inner = cv2.resize(inner, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_AREA)
    return inner


# ======================================================
# AUGMENT
# ======================================================

def augment(img):
    h, w = img.shape

    angle = random.uniform(-12, 12)
    scale = random.uniform(0.9, 1.1)
    tx = random.uniform(-0.05 * w, 0.05 * w)
    ty = random.uniform(-0.05 * h, 0.05 * h)

    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    M[:, 2] += (tx, ty)

    img = cv2.warpAffine(img, M, (w, h), borderValue=0)

    if random.random() < 0.3:
        img = cv2.GaussianBlur(img, (3, 3), 0)

    return img


# ======================================================
# LOAD DATASET
# ======================================================

def load_dataset():

    CONDITIONS = ["extreme", "mild", "normal", "strong"]

    X_train, y_train = [], []
    X_val, y_val = [], []
    X_test, y_test = [], []

    print("=" * 60, flush=True)
    print("[DATASET] Začínam načítavanie datasetu...", flush=True)
    print(f"[DATASET] Root: {DATASET_ROOT}", flush=True)
    print(f"[DATASET] Triedy: {SPEED_CLASSES}", flush=True)
    print(f"[DATASET] Podmienky: {CONDITIONS}", flush=True)
    print("=" * 60, flush=True)

    dataset_load_start = time.perf_counter()

    for idx, speed in enumerate(SPEED_CLASSES):

        speed_folder = DATASET_ROOT / str(speed)

        if not speed_folder.exists():
            print(f"[WARN] Priečinok neexistuje, preskakujem: {speed_folder}", flush=True)
            continue

        class_start = time.perf_counter()
        class_count = 0

        for cond in CONDITIONS:

            cond_folder = speed_folder / cond

            if not cond_folder.exists():
                print(f"  [WARN] Podmienka neexistuje, preskakujem: {cond_folder}", flush=True)
                continue

            cond_start = time.perf_counter()
            images = list(cond_folder.glob("*"))

            random.shuffle(images)

            n = len(images)
            print(f"  [LOAD] Trieda {speed:>3} / {cond:<8} | {n} obrázkov", end="", flush=True)

            n_train = int(0.70 * n)
            n_val = int(0.15 * n)
            n_test = n - n_train - n_val

            train_imgs = images[:n_train]
            val_imgs = images[n_train:n_train + n_val]
            test_imgs = images[n_train + n_val:n_train + n_val + n_test]

            skipped = 0

            # TRAIN
            for i, p in enumerate(train_imgs):
                img = cv2.imread(str(p))
                if img is None:
                    skipped += 1
                    continue

                patch = preprocess(img, speed)

                X_train.append(patch.flatten() / 255.0)
                y_train.append(idx)

                for _ in range(2):
                    aug = augment(patch)
                    X_train.append(aug.flatten() / 255.0)
                    y_train.append(idx)

                if (i + 1) % 1000 == 0:
                    print(f" [train {i+1}/{n_train}]", end="", flush=True)

            # VAL
            for p in val_imgs:
                img = cv2.imread(str(p))
                if img is None:
                    skipped += 1
                    continue

                patch = preprocess(img, speed)

                X_val.append(patch.flatten() / 255.0)
                y_val.append(idx)

            # TEST
            for p in test_imgs:
                img = cv2.imread(str(p))
                if img is None:
                    skipped += 1
                    continue

                patch = preprocess(img, speed)

                X_test.append(patch.flatten() / 255.0)
                y_test.append(idx)

            cond_time = time.perf_counter() - cond_start
            class_count += n
            skip_info = f" (preskočených: {skipped})" if skipped > 0 else ""
            print(f" | hotovo za {cond_time:.1f}s{skip_info}", flush=True)

        class_time = time.perf_counter() - class_start
        print(f"  [OK] Trieda {speed} kompletná: {class_count} obrázkov za {class_time:.1f}s", flush=True)

    print("-" * 60, flush=True)
    print(f"[DATASET] Načítaných: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}", flush=True)
    print("[DATASET] Konvertujem na tensory...", flush=True)

    tensor_start = time.perf_counter()
    X_train = torch.tensor(np.array(X_train), dtype=torch.float32)
    y_train = torch.tensor(np.array(y_train), dtype=torch.long)

    X_val = torch.tensor(np.array(X_val), dtype=torch.float32)
    y_val = torch.tensor(np.array(y_val), dtype=torch.long)

    X_test = torch.tensor(np.array(X_test), dtype=torch.float32)
    y_test = torch.tensor(np.array(y_test), dtype=torch.long)
    tensor_time = time.perf_counter() - tensor_start

    dataset_load_time = time.perf_counter() - dataset_load_start

    print(f"[DATASET] Tensor konverzia za {tensor_time:.1f}s", flush=True)
    print(f"[DATASET] TRAIN: {X_train.shape}", flush=True)
    print(f"[DATASET] VAL:   {X_val.shape}", flush=True)
    print(f"[DATASET] TEST:  {X_test.shape}", flush=True)
    print(f"[DATASET] Celkový čas načítavania: {dataset_load_time:.1f}s", flush=True)
    print("=" * 60, flush=True)

    return X_train, y_train, X_val, y_val, X_test, y_test

# ======================================================
# MODEL
# ======================================================

class SpeedMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(INPUT_DIM, 128)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(128, len(SPEED_CLASSES))

    def forward(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x


# ======================================================
# REPORT HELPERS
# ======================================================

def ensure_report_dir():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def save_training_log_csv(rows, out_path: Path):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["epoch", "train_loss", "val_acc", "best_val_acc", "lr", "epoch_time_sec"])
        for r in rows:
            w.writerow(r)


def plot_curve(xs, ys, title, xlabel, ylabel, out_path: Path):
    plt.figure(figsize=(10, 6))
    plt.plot(xs, ys, linewidth=2)
    plt.title(title, fontsize=20, fontweight="bold", pad=14)
    plt.xlabel(xlabel, fontsize=16, fontweight="bold", labelpad=10)
    plt.ylabel(ylabel, fontsize=16, fontweight="bold", labelpad=10)
    plt.xticks(fontsize=13)
    plt.yticks(fontsize=13)
    plt.tight_layout()
    plt.savefig(out_path, dpi=240)
    plt.close()


def plot_loss_vs_time(train_losses, epoch_times, out_path: Path):
    plt.figure(figsize=(10, 6))
    plt.scatter(epoch_times, train_losses, s=60)
    plt.title("Loss vs Epoch Time (stability check)", fontsize=20, fontweight="bold", pad=14)
    plt.xlabel("Epoch time (sec)", fontsize=16, fontweight="bold", labelpad=10)
    plt.ylabel("Train loss", fontsize=16, fontweight="bold", labelpad=10)
    plt.xticks(fontsize=13)
    plt.yticks(fontsize=13)
    plt.tight_layout()
    plt.savefig(out_path, dpi=240)
    plt.close()


def compute_confusion_matrix(y_true, y_pred, num_classes: int):
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        cm[int(t), int(p)] += 1
    return cm


def save_confusion_matrix_png(cm, class_labels, out_path: Path, normalize: bool = False):
    # aby "d" formát fungoval pre nenormalizovanú CM
    if normalize:
        cm_to_show = cm.astype(np.float32)
    else:
        cm_to_show = cm.astype(np.int64)

    if normalize:
        row_sums = cm_to_show.sum(axis=1, keepdims=True) + 1e-9
        cm_to_show = cm_to_show / row_sums

    fig, ax = plt.subplots(figsize=(14, 12))
    im = ax.imshow(cm_to_show, interpolation="nearest")

    ax.set_title(
        "Confusion Matrix" + (" (Normalized)" if normalize else ""),
        fontsize=26,
        fontweight="bold",
        pad=18,
    )
    cbar = fig.colorbar(im, ax=ax)
    cbar.ax.tick_params(labelsize=14)

    ticks = np.arange(len(class_labels))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels(class_labels, fontsize=16, fontweight="bold", rotation=45, ha="right")
    ax.set_yticklabels(class_labels, fontsize=16, fontweight="bold")

    fmt = ".2f" if normalize else "d"
    thresh = float(np.max(cm_to_show)) * 0.6 if cm_to_show.size else 0.0

    for i in range(cm_to_show.shape[0]):
        for j in range(cm_to_show.shape[1]):
            val = cm_to_show[i, j]
            if normalize:
                text = format(float(val), fmt)
                v_for_color = float(val)
            else:
                text = format(int(val), fmt)
                v_for_color = float(val)

            ax.text(
                j,
                i,
                text,
                ha="center",
                va="center",
                fontsize=14,
                fontweight="bold",
                color="white" if v_for_color > thresh else "black",
            )

    ax.set_ylabel("True label", fontsize=18, fontweight="bold", labelpad=12)
    ax.set_xlabel("Predicted label", fontsize=18, fontweight="bold", labelpad=12)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()


def highlight_classes_on_cm_png(class_labels, highlight_labels, out_path: Path, color="red"):
    img = cv2.imread(str(out_path))
    if img is None:
        return

    n = len(class_labels)
    if n <= 0:
        return

    h, w = img.shape[:2]
    left = int(0.18 * w)
    right = int(0.96 * w)
    top = int(0.10 * h)
    bottom = int(0.92 * h)

    plot_w = right - left
    plot_h = bottom - top
    cell_w = plot_w / n
    cell_h = plot_h / n

    if color == "red":
        col = (0, 0, 255)
    elif color == "green":
        col = (0, 255, 0)
    else:
        col = (255, 0, 0)

    thickness = max(2, int(min(h, w) * 0.003))

    idxs = []
    for hl in highlight_labels:
        if hl in class_labels:
            idxs.append(class_labels.index(hl))

    for i in idxs:
        y0 = int(top + i * cell_h)
        y1 = int(top + (i + 1) * cell_h)
        cv2.rectangle(img, (left, y0), (right, y1), col, thickness)

        x0 = int(left + i * cell_w)
        x1 = int(left + (i + 1) * cell_w)
        cv2.rectangle(img, (x0, top), (x1, bottom), col, thickness)

    cv2.imwrite(str(out_path), img)


def classification_report_from_cm(cm, class_labels):
    report_lines = []
    report_lines.append("class,precision,recall,f1,support\n")

    tp = np.diag(cm).astype(np.float32)
    support = cm.sum(axis=1).astype(np.float32)
    pred_sum = cm.sum(axis=0).astype(np.float32)

    precision = tp / (pred_sum + 1e-9)
    recall = tp / (support + 1e-9)
    f1 = 2 * precision * recall / (precision + recall + 1e-9)

    for i, lbl in enumerate(class_labels):
        report_lines.append(f"{lbl},{precision[i]:.4f},{recall[i]:.4f},{f1[i]:.4f},{int(support[i])}\n")

    report_lines.append(
        f"macro_avg,{precision.mean():.4f},{recall.mean():.4f},{f1.mean():.4f},{int(support.sum())}\n"
    )
    acc = tp.sum() / (cm.sum() + 1e-9)
    report_lines.append(f"accuracy,{acc:.4f},,,{int(support.sum())}\n")
    return "".join(report_lines)


def auto_open_folder(path: Path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))
        elif sys.platform.startswith("darwin"):
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


# ======================================================
# FLOPs / MACs
# ======================================================

def count_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


def estimate_macs_flops_for_mlp(input_dim: int, hidden_dim: int, out_dim: int):
    macs = input_dim * hidden_dim + hidden_dim * out_dim
    flops = 2 * macs
    return macs, flops


# ======================================================
# TRAINING (GPU)
# ======================================================

def train():
    print("=" * 60, flush=True)
    print("[START] Spúšťam trénovací pipeline...", flush=True)
    print(f"[START] Čas: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print("=" * 60, flush=True)

    ensure_report_dir()

    # device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_cuda = (device.type == "cuda")
    use_amp = bool(USE_AMP and use_cuda)

    if use_cuda:
        print(f"[INFO] Používam GPU: {torch.cuda.get_device_name(0)}", flush=True)
        print(f"[INFO] GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB", flush=True)
    else:
        print("[INFO] Používam CPU (CUDA nie je dostupná)", flush=True)

    print(f"[INFO] AMP (mixed precision): {use_amp}", flush=True)
    print(f"[INFO] Batch size: {BATCH_SIZE}, Epochs: {EPOCHS}, LR: {LR}", flush=True)

    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = REPORT_DIR / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Report dir: {run_dir}", flush=True)

    print("\n[STEP 1/5] Načítavanie datasetu...", flush=True)
    X_train, y_train, X_val, y_val, X_test, y_test = load_dataset()

    print("\n[STEP 2/5] Príprava DataLoaderov...", flush=True)
    train_set = TensorDataset(X_train, y_train)
    val_set = TensorDataset(X_val, y_val)
    test_set = TensorDataset(X_test, y_test)

    # DataLoader optimalizácie: pin_memory pomáha len na CUDA
    train_loader = DataLoader(
        train_set,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=NUM_WORKERS,
        pin_memory=(PIN_MEMORY and use_cuda),
        persistent_workers=(NUM_WORKERS > 0)
    )
    val_loader = DataLoader(
        val_set,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=NUM_WORKERS,
        pin_memory=(PIN_MEMORY and use_cuda),
        persistent_workers=(NUM_WORKERS > 0)
    )

    print(f"[INFO] Train batches: {len(train_loader)}, Val batches: {len(val_loader)}", flush=True)

    model = SpeedMLP().to(device)
    optimizer = optim.Adam(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    criterion = nn.CrossEntropyLoss()

    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    print(f"[INFO] Model parametrov: {count_params(model)}", flush=True)

    best_val_acc = 0.0

    epochs = []
    train_losses = []
    val_accs = []
    epoch_times = []
    csv_rows = []

    print(f"\n[STEP 3/5] Trénovanie ({EPOCHS} epoch)...", flush=True)
    print("-" * 60, flush=True)
    train_start_time = time.perf_counter()

    for epoch in range(EPOCHS):
        epoch_start = time.perf_counter()

        # ---------------- TRAIN ----------------
        model.train()
        total_loss = 0.0
        num_batches = 0
        total_train_batches = len(train_loader)

        for batch_idx, (xb, yb) in enumerate(train_loader):
            # presun na GPU
            xb = xb.to(device, non_blocking=True)
            yb = yb.to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)

            with torch.cuda.amp.autocast(enabled=use_amp):
                out = model(xb)
                loss = criterion(out, yb)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            total_loss += float(loss.detach().item())
            num_batches += 1

            # Progress každých 10 batchov alebo posledný batch
            if (batch_idx + 1) % 10 == 0 or (batch_idx + 1) == total_train_batches:
                print(f"  [TRAIN] Epoch {epoch+1}/{EPOCHS} | Batch {batch_idx+1}/{total_train_batches} | Loss: {float(loss.item()):.4f}", flush=True)

        avg_train_loss = total_loss / max(1, num_batches)

        # ---------------- VALIDATION ----------------
        model.eval()
        correct = 0
        total = 0
        total_val_batches = len(val_loader)

        print(f"  [VAL] Epoch {epoch+1}/{EPOCHS} | Validácia ({total_val_batches} batchov)...", flush=True)

        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device, non_blocking=True)
                yb = yb.to(device, non_blocking=True)

                with torch.cuda.amp.autocast(enabled=use_amp):
                    out = model(xb)
                preds = torch.argmax(out, dim=1)
                correct += (preds == yb).sum().item()
                total += yb.size(0)

        val_acc = 100.0 * correct / max(1, total)

        # time
        epoch_time = time.perf_counter() - epoch_start

        # ak CUDA: presnejšie časovanie (voliteľné)
        if use_cuda:
            torch.cuda.synchronize()

        print(f"  >>> Epoch {epoch + 1}/{EPOCHS} | TrainLoss={avg_train_loss:.4f} | ValAcc={val_acc:.2f}% | Čas={epoch_time:.2f}s", flush=True)

        epochs.append(epoch + 1)
        train_losses.append(avg_train_loss)
        val_accs.append(val_acc)
        epoch_times.append(epoch_time)

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            # ukladáme CPU kompatibilne
            torch.save({
                "state_dict": model.state_dict(),
                "class_labels": SPEED_CLASSES,
                "img_size": IMG_SIZE,
                "device_trained": str(device)
            }, MODEL_PATH)
            print(f"  >>> Najlepší model uložený! (ValAcc={best_val_acc:.2f}%)", flush=True)

        current_lr = optimizer.param_groups[0]["lr"]
        csv_rows.append([epoch + 1, avg_train_loss, val_acc, best_val_acc, current_lr, epoch_time])
        print("-" * 60, flush=True)

    total_training_time = time.perf_counter() - train_start_time
    avg_epoch_time = float(sum(epoch_times) / max(1, len(epoch_times)))

    print(f"\n[STEP 4/5] Trénovanie dokončené!", flush=True)
    print(f"[INFO] Celkový čas trénovania: {total_training_time:.2f} s", flush=True)
    print(f"[INFO] Priemerný čas epochy: {avg_epoch_time:.2f} s", flush=True)
    print(f"[INFO] Najlepšia ValAcc: {best_val_acc:.2f}%", flush=True)

    # =========================
    # SAVE CSV + PLOTS
    # =========================
    print("\n[STEP 5/5] Generovanie reportov a grafov...", flush=True)
    save_training_log_csv(csv_rows, run_dir / "training_log.csv")
    print("  [OK] training_log.csv uložený", flush=True)

    plot_curve(epochs, train_losses, "Training Loss", "Epoch", "Loss", run_dir / "loss_curve.png")
    print("  [OK] loss_curve.png", flush=True)
    plot_curve(epochs, val_accs, "Validation Accuracy", "Epoch", "Accuracy (%)", run_dir / "val_accuracy_curve.png")
    print("  [OK] val_accuracy_curve.png", flush=True)
    plot_curve(epochs, epoch_times, "Epoch Time", "Epoch", "Time (sec)", run_dir / "epoch_time_curve.png")
    print("  [OK] epoch_time_curve.png", flush=True)
    plot_loss_vs_time(train_losses, epoch_times, run_dir / "loss_vs_epoch_time.png")
    print("  [OK] loss_vs_epoch_time.png", flush=True)

    # =========================
    # CONFUSION MATRIX (VAL) using BEST model
    # =========================
    print("  [INFO] Generujem confusion matrix...", flush=True)
    ckpt = torch.load(MODEL_PATH, map_location=device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    y_true = []
    y_pred = []

    with torch.no_grad():
        for xb, yb in val_loader:
            xb = xb.to(device, non_blocking=True)
            yb = yb.to(device, non_blocking=True)

            with torch.cuda.amp.autocast(enabled=use_amp):
                out = model(xb)

            preds = torch.argmax(out, dim=1)
            y_true.extend(yb.detach().cpu().numpy().tolist())
            y_pred.extend(preds.detach().cpu().numpy().tolist())

    cm = compute_confusion_matrix(y_true, y_pred, num_classes=len(SPEED_CLASSES))
    labels_str = [str(s) for s in SPEED_CLASSES]

    cm_path = run_dir / "confusion_matrix.png"
    cmn_path = run_dir / "confusion_matrix_norm.png"
    save_confusion_matrix_png(cm, labels_str, cm_path, normalize=False)
    save_confusion_matrix_png(cm, labels_str, cmn_path, normalize=True)

    highlight = ["100", "110", "130"]
    highlight_classes_on_cm_png(labels_str, highlight, cm_path, color="red")
    highlight_classes_on_cm_png(labels_str, highlight, cmn_path, color="red")

    idxs = [labels_str.index(s) for s in highlight if s in labels_str]
    confusion_100_110_130 = 0
    total_100_110_130 = 0
    if len(idxs) == 3:
        total_100_110_130 = int(cm[idxs, :].sum())
        for ti in idxs:
            for pj in idxs:
                if ti != pj:
                    confusion_100_110_130 += int(cm[ti, pj])
    confusion_rate = (100.0 * confusion_100_110_130 / total_100_110_130) if total_100_110_130 > 0 else 0.0

    report_csv_text = classification_report_from_cm(cm, labels_str)
    (run_dir / "classification_report.csv").write_text(report_csv_text, encoding="utf-8")

    final_acc = (np.trace(cm) / (cm.sum() + 1e-9)) * 100.0

    # FLOPs/Params
    params = count_params(model)
    macs, flops = estimate_macs_flops_for_mlp(INPUT_DIM, 128, len(SPEED_CLASSES))

    # summary
    summary = (
        f"RUN: {run_id}\n"
        f"Device: {device}\n"
        f"GPU name: {torch.cuda.get_device_name(0) if use_cuda else 'N/A'}\n"
        f"AMP: {use_amp}\n"
        f"\n"
        f"Dataset root: {DATASET_ROOT}\n"
        f"Model path: {MODEL_PATH}\n"
        f"\n"
        f"IMG_SIZE: {IMG_SIZE}\n"
        f"INPUT_DIM: {INPUT_DIM}\n"
        f"HIDDEN: 128\n"
        f"CLASSES: {len(SPEED_CLASSES)}\n"
        f"BATCH_SIZE: {BATCH_SIZE}\n"
        f"EPOCHS: {EPOCHS}\n"
        f"LR: {LR}\n"
        f"WEIGHT_DECAY: {WEIGHT_DECAY}\n"
        f"\n"
        f"Training time statistics:\n"
        f"- Total training time: {total_training_time:.2f} sec\n"
        f"- Average epoch time: {avg_epoch_time:.2f} sec\n"
        f"\n"
        f"Results:\n"
        f"- Best ValAcc (during training): {best_val_acc:.2f}%\n"
        f"- Final ValAcc (best model, CM): {final_acc:.2f}%\n"
        f"\n"
        f"Komisia-friendly:\n"
        f"- Zámennosť medzi triedami 100/110/130: {confusion_rate:.2f}% (pozri confusion_matrix*.png – zvýraznené červeným rámčekom)\n"
        f"\n"
        f"Model complexity:\n"
        f"- Parameters: {params}\n"
        f"- MACs (1 forward): {macs}\n"
        f"- FLOPs (approx, 2*MACs): {flops}\n"
        f"\n"
        f"Outputs:\n"
        f"- training_log.csv\n"
        f"- loss_curve.png\n"
        f"- val_accuracy_curve.png\n"
        f"- epoch_time_curve.png\n"
        f"- loss_vs_epoch_time.png\n"
        f"- confusion_matrix.png\n"
        f"- confusion_matrix_norm.png\n"
        f"- classification_report.csv\n"
    )
    (run_dir / "summary.txt").write_text(summary, encoding="utf-8")

    print(f"\n[OK] Training report saved to: {run_dir}", flush=True)
    print("=" * 60, flush=True)
    print("[DONE] Celý pipeline dokončený!", flush=True)
    print(f"[DONE] Čas: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print("=" * 60, flush=True)
    auto_open_folder(run_dir)


if __name__ == "__main__":
    train()
