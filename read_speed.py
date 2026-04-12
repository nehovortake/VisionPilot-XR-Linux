# qt_read_sign.py (pôvodný - funguje správne!)
# ------------------------------------------------------
# MLP (PyTorch) reader – reads speed from ellipse crop (BGR)
# - loads: dataset/mlp_speed_model.pt
# - preprocess variants: crop (2-digit) + pad (3-digit safe)
# - stabilization: confidence gate (margin) + majority vote
# ------------------------------------------------------

from __future__ import annotations
from pathlib import Path
from collections import deque

import numpy as np
import cv2

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    print("[read_speed] Warning: PyTorch not installed, speed reader will be disabled")
    torch = None
    nn = None
    TORCH_AVAILABLE = False


# ======================================================
# CONFIG
# ======================================================

# Use relative path from script location (works on Windows, Linux, Jetson)
SCRIPT_ROOT = Path(__file__).resolve().parent
DATASET_ROOT = SCRIPT_ROOT / "dataset"
MODEL_PATH = DATASET_ROOT / "mlp_speed_model_dataset_split.pt"

# ======================================================
# RUNTIME PREPROCESS VARIANTS
# - default: best for 2-digit (10..90)
# - three_pad: protects 100/110/130 from cutting (pad-to-square)
# NOTE: MLP was trained with:
#   - 2-digit: crop (inner_scale=0.75, focus=0.90)
#   - 3-digit: pad  (inner_scale=1.00, focus=1.00)
# ======================================================

RUNTIME_PREPROCESS_VARIANTS = [
    ("default",   {"inner_scale": None,  "focus_scale": None, "crop_mode": "crop"}),  # use model defaults
    ("three_pad", {"inner_scale": 1.00,  "focus_scale": 1.00, "crop_mode": "pad"}),   # 3-digit safe
]


# ======================================================
# PREPROCESS (must match training logic)
# ======================================================

def preprocess_inner_mask(
    img_bgr: np.ndarray,
    out_size: int = 64,
    inner_scale: float = 0.75,
    focus_scale: float = 0.90,
    crop_mode: str = "crop",
) -> np.ndarray | None:
    """
    1) grayscale + blur
    2) inner circular mask (suppresses ring)
    3) crop mode:
       - crop: center crop using min(h,w)
       - pad : pad to square first (prevents cutting 3-digit), then optional focus crop
    4) resize to out_size x out_size
    """
    if img_bgr is None or img_bgr.size == 0:
        return None

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    h, w = gray.shape
    cx, cy = w // 2, h // 2

    # 1) inner circular mask
    r = int(inner_scale * 0.5 * min(w, h))
    mask = np.zeros_like(gray, np.uint8)
    cv2.circle(mask, (cx, cy), r, 255, -1)
    inner = cv2.bitwise_and(gray, gray, mask=mask)

    # 2) crop / pad
    if crop_mode == "pad":
        h2, w2 = inner.shape
        s0 = max(h2, w2)
        canvas = np.zeros((s0, s0), dtype=inner.dtype)

        y_off = (s0 - h2) // 2
        x_off = (s0 - w2) // 2
        canvas[y_off:y_off + h2, x_off:x_off + w2] = inner

        # optional zoom AFTER padding
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

    # 3) resize
    inner = cv2.resize(inner, (out_size, out_size), interpolation=cv2.INTER_AREA)
    return inner


# ======================================================
# MLP MODEL DEFINITION (must match training)
# ======================================================

if TORCH_AVAILABLE:
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
    SpeedMLP = None


# ======================================================
# READER CLASS (QT SAFE)
# ======================================================

if TORCH_AVAILABLE:
    class PerceptronSpeedReader:
        """
        Historical name kept for compatibility with the rest of your project.
        Now it uses PyTorch MLP internally.
        """

        def __init__(self, model_path: Path = MODEL_PATH):
            # model + meta
            self.model: SpeedMLP | None = None
            self.labels: list[int] | None = None
            self.img_size: int = 64

            # defaults (used when variant says None)
            # NOTE: these are only defaults. For 3-digit we override via variants.
            self.inner_scale: float = 0.75
            self.focus_scale: float = 0.90

            # ==========================
            # RUNTIME STABILIZATION
            # ==========================
            self.pred_hist = deque(maxlen=7)  # last N confident predictions
            self.last_stable: int | None = None
            self.min_margin = 0.15            # confidence threshold (top1-top2) - lowered from 0.35
            self.min_votes = 4                # votes required to accept winner

            self._load_model(model_path)

        def _load_model(self, path: Path):
            if not path.exists():
                raise FileNotFoundError(f"MLP model not found: {path}")

            device = "cuda" if torch.cuda.is_available() else "cpu"
            checkpoint = torch.load(str(path), map_location=device)

            # required keys from training save
            class_labels = checkpoint.get("class_labels", None)
            if class_labels is None:
                raise KeyError("Missing 'class_labels' in .pt checkpoint")

            self.labels = [int(x) for x in class_labels]
            self.img_size = int(checkpoint.get("img_size", 64))

            self.model = SpeedMLP(num_classes=len(self.labels))
            state = checkpoint["state_dict"]

            # ------------------------------------------------------
            # BACKWARD COMPAT: starý model ukladal fc1/fc2,
            # nový model má nn.Sequential -> net.0 / net.2
            # ------------------------------------------------------
            if ("fc1.weight" in state) and ("net.0.weight" not in state):
                state = {
                    "net.0.weight": state["fc1.weight"],
                    "net.0.bias": state["fc1.bias"],
                    "net.2.weight": state["fc2.weight"],
                    "net.2.bias": state["fc2.bias"],
                }

            # (voliteľné) aj opačný smer, keby si niekedy načítal nový checkpoint do starého runtime
            if ("net.0.weight" in state) and ("fc1.weight" not in state) and hasattr(self.model, "fc1"):
                state = {
                    "fc1.weight": state["net.0.weight"],
                    "fc1.bias": state["net.0.bias"],
                    "fc2.weight": state["net.2.weight"],
                    "fc2.bias": state["net.2.bias"],
                }

            self.model.load_state_dict(state, strict=True)

            if torch.cuda.is_available():
                try:
                    self.model = self.model.to("cuda")
                except Exception:
                    pass

            self.model.eval()

            print(f"[MLP] Loaded | classes={self.labels} | img={self.img_size} | device={next(self.model.parameters()).device}")

        # --------------------------------------------------
        # helpers
        # --------------------------------------------------
        @staticmethod
        def _margin_top1_top2(logits_1d: np.ndarray) -> float:
            """top1 - top2 margin (bigger = more confident)"""
            if logits_1d is None or logits_1d.size == 0:
                return -1e9
            if logits_1d.size == 1:
                return float(logits_1d[0])
            top2 = np.partition(logits_1d, -2)[-2:]
            # top2 contains two largest (unordered)
            return float(top2.max() - top2.min())

        # ==================================================
        # MAIN API – CALL THIS FROM IMAGE PROCESSOR
        # ==================================================
        def predict_from_crop(self, crop_bgr: np.ndarray) -> int | None:
            """
            crop_bgr : np.ndarray (BGR) – ellipse crop
            return   : int | None (speed km/h)
            """
            try:
                if crop_bgr is None or crop_bgr.size == 0:
                    return self.last_stable

                if self.model is None or self.labels is None:
                    return self.last_stable

                best_label: int | None = None
                best_margin: float = -1e9
                best_maxlogit: float = -1e9
                variant_count = 0

                # try multiple preprocessing variants and pick the most confident
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

                    x = (patch.astype(np.float32) / 255.0).reshape(1, -1)  # (1,4096)
                    x_tensor = torch.from_numpy(x)
                    try:
                        x_tensor = x_tensor.to(next(self.model.parameters()).device)
                    except Exception:
                        pass

                    with torch.no_grad():
                        out = self.model(x_tensor)  # (1,num_classes)

                    logits = out.squeeze(0).cpu().numpy()
                    idx = int(np.argmax(logits))

                    # Validate index is within range
                    if idx < 0 or idx >= len(self.labels):
                        continue

                    pred_label = int(self.labels[idx])

                    margin = self._margin_top1_top2(logits)
                    maxlogit = float(logits[idx])

                    variant_count += 1

                    # pick: higher margin, tie-break by higher maxlogit
                    if (margin > best_margin) or (margin == best_margin and maxlogit > best_maxlogit):
                        best_margin = margin
                        best_maxlogit = maxlogit
                        best_label = pred_label

                # nothing worked
                if best_label is None:
                    return self.last_stable

                # ==========================
                # 1) CONFIDENCE GATE
                # ==========================
                if best_margin < self.min_margin:
                    return self.last_stable

                # ==========================
                # 2) TEMPORAL STABILIZATION (majority vote)
                # ==========================
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
                print("[MLP] Prediction error:", e)
                return self.last_stable

else:
    # PyTorch not available - provide dummy class
    class PerceptronSpeedReader:
        def __init__(self, *args, **kwargs):
            # Silent initialization - warning already shown at import time
            self.model = None

        def predict_from_crop(self, crop_bgr):
            """Without PyTorch, cannot classify speed - return None."""
            return None

