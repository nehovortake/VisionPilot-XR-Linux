from __future__ import annotations

import ctypes
import os
import platform
from collections import deque
from pathlib import Path

import cv2
import numpy as np

# ------------------------------------------------------
# Jetson-safe PyTorch preload
# ------------------------------------------------------
_TORCH_IMPORT_ERROR = None
_TORCH_OK = False

if platform.system() == "Linux" and platform.machine() in ("aarch64", "arm64"):
    for lib in (
        "/usr/lib/aarch64-linux-gnu/libgomp.so.1",
        "/lib/aarch64-linux-gnu/libgomp.so.1",
    ):
        try:
            ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
            print(f"[MLP] Preloaded: {lib}")
            break
        except Exception:
            pass

try:
    import torch
    import torch.nn as nn
    _TORCH_OK = True
except Exception as e:
    torch = None
    nn = None
    _TORCH_IMPORT_ERROR = e


SCRIPT_ROOT = Path(__file__).resolve().parent
DATASET_ROOT = SCRIPT_ROOT / "dataset"
MODEL_PATHS = [
    DATASET_ROOT / "mlp_speed_model_dataset_split.pt",
    DATASET_ROOT / "mlp_speed_model.pt",
]
MODEL_PATH = next((p for p in MODEL_PATHS if p.exists()), MODEL_PATHS[0])

RUNTIME_PREPROCESS_VARIANTS = [
    ("default", {"inner_scale": None, "focus_scale": None, "crop_mode": "crop"}),
    ("three_pad", {"inner_scale": 1.00, "focus_scale": 1.00, "crop_mode": "pad"}),
]


def preprocess_inner_mask(
    img_bgr: np.ndarray,
    out_size: int = 64,
    inner_scale: float = 0.75,
    focus_scale: float = 0.90,
    crop_mode: str = "crop",
) -> np.ndarray | None:
    if img_bgr is None or img_bgr.size == 0:
        return None

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    h, w = gray.shape
    cx, cy = w // 2, h // 2

    r = int(inner_scale * 0.5 * min(w, h))
    mask = np.zeros_like(gray, np.uint8)
    cv2.circle(mask, (cx, cy), r, 255, -1)
    inner = cv2.bitwise_and(gray, gray, mask=mask)

    if crop_mode == "pad":
        h2, w2 = inner.shape
        s0 = max(h2, w2)
        canvas = np.zeros((s0, s0), dtype=inner.dtype)
        y_off = (s0 - h2) // 2
        x_off = (s0 - w2) // 2
        canvas[y_off:y_off + h2, x_off:x_off + w2] = inner

        s = int(s0 * focus_scale)
        s = max(8, min(s, s0))
        cx2 = cy2 = s0 // 2
        x0 = max(0, cx2 - s // 2)
        y0 = max(0, cy2 - s // 2)
        x0 = min(x0, s0 - s)
        y0 = min(y0, s0 - s)
        inner = canvas[y0:y0 + s, x0:x0 + s]
    else:
        s0 = min(h, w)
        s = int(s0 * focus_scale)
        s = max(8, min(s, s0))
        x0 = max(0, cx - s // 2)
        y0 = max(0, cy - s // 2)
        x0 = min(x0, w - s)
        y0 = min(y0, h - s)
        inner = inner[y0:y0 + s, x0:x0 + s]

    inner = cv2.resize(inner, (out_size, out_size), interpolation=cv2.INTER_AREA)
    return inner


if _TORCH_OK:
    class SpeedMLP(nn.Module):
        def __init__(self, num_classes: int):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(4096, 128),
                nn.ReLU(),
                nn.Linear(128, num_classes),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.net(x)
else:
    class SpeedMLP:
        def __init__(self, num_classes: int):
            raise RuntimeError(f"PyTorch unavailable: {_TORCH_IMPORT_ERROR}")


class PerceptronSpeedReader:
    def __init__(self, model_path: Path = MODEL_PATH):
        if not _TORCH_OK:
            raise ImportError(f"PyTorch import failed: {_TORCH_IMPORT_ERROR}")

        self.model = None
        self.labels: list[int] | None = None
        self.img_size: int = 64
        self.inner_scale: float = 0.75
        self.focus_scale: float = 0.90
        self.pred_hist = deque(maxlen=7)
        self.last_stable: int | None = None
        self.min_margin = 0.35
        self.min_votes = 4
        self.min_softmax_prob = 0.9
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._load_model(model_path)

    def _load_model(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"MLP model not found: {path}")

        checkpoint = torch.load(str(path), map_location=self.device)
        class_labels = checkpoint.get("class_labels", None)
        if class_labels is None:
            raise KeyError("Missing 'class_labels' in .pt checkpoint")

        self.labels = [int(x) for x in class_labels]
        self.img_size = int(checkpoint.get("img_size", 64))
        self.model = SpeedMLP(num_classes=len(self.labels))
        state = checkpoint["state_dict"]

        if ("fc1.weight" in state) and ("net.0.weight" not in state):
            state = {
                "net.0.weight": state["fc1.weight"],
                "net.0.bias": state["fc1.bias"],
                "net.2.weight": state["fc2.weight"],
                "net.2.bias": state["fc2.bias"],
            }

        self.model.load_state_dict(state, strict=True)
        self.model = self.model.to(self.device)
        self.model.eval()
        print(f"[MLP] Loaded | classes={self.labels} | img={self.img_size} | device={self.device} | model={path.name}")

    @staticmethod
    def _margin_top1_top2(logits_1d: np.ndarray) -> float:
        if logits_1d is None or logits_1d.size == 0:
            return -1e9
        if logits_1d.size == 1:
            return float(logits_1d[0])
        top2 = np.partition(logits_1d, -2)[-2:]
        return float(top2.max() - top2.min())

    def predict_from_crop(self, crop_bgr: np.ndarray) -> int | None:
        try:
            if crop_bgr is None or crop_bgr.size == 0:
                return self.last_stable
            if self.model is None or self.labels is None:
                return self.last_stable

            best_label: int | None = None
            best_margin: float = -1e9
            best_prob: float = 0.0

            for _name, cfg in RUNTIME_PREPROCESS_VARIANTS:
                inner_scale = self.inner_scale if cfg.get("inner_scale") is None else float(cfg["inner_scale"])
                focus_scale = self.focus_scale if cfg.get("focus_scale") is None else float(cfg["focus_scale"])
                crop_mode = cfg.get("crop_mode", "crop")

                patch = preprocess_inner_mask(
                    crop_bgr,
                    out_size=self.img_size,
                    inner_scale=inner_scale,
                    focus_scale=focus_scale,
                    crop_mode=crop_mode,
                )
                if patch is None:
                    continue

                x = (patch.astype(np.float32) / 255.0).reshape(1, -1)
                x_tensor = torch.from_numpy(x).to(self.device)

                with torch.no_grad():
                    out = self.model(x_tensor)

                logits = out.squeeze(0).detach().cpu().numpy()
                exp_logits = np.exp(logits - logits.max())
                probs = exp_logits / exp_logits.sum()

                idx = int(np.argmax(probs))
                pred_label = int(self.labels[idx])
                top_prob = float(probs[idx])
                margin = self._margin_top1_top2(logits)

                if (top_prob > best_prob) or (top_prob == best_prob and margin > best_margin):
                    best_margin = margin
                    best_label = pred_label
                    best_prob = top_prob

            if best_label is None:
                return self.last_stable
            if best_prob < self.min_softmax_prob:
                return self.last_stable
            if best_margin < self.min_margin:
                return self.last_stable

            self.pred_hist.append(best_label)
            counts: dict[int, int] = {}
            for v in self.pred_hist:
                counts[v] = counts.get(v, 0) + 1
            winner, votes = max(counts.items(), key=lambda kv: kv[1])
            if votes < self.min_votes:
                return self.last_stable

            self.last_stable = winner
            return self.last_stable
        except Exception as e:
            print(f"[MLP] Prediction error: {e}")
            return self.last_stable
