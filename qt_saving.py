import os
import cv2
import time
import threading
from queue import Queue
from datetime import datetime


class EllipseSaver:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

        self.session_dir = None
        self.ellipse_dir = None
        self.counter = 0
        self.enabled = False

        self.queue = Queue(maxsize=500)
        self.worker = None
        self.running = False

    # =========================
    # SESSION
    # =========================
    def start_session(self):
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_dir = os.path.join(self.base_dir, ts)
        self.ellipse_dir = os.path.join(self.session_dir, "detected_ellipses")
        os.makedirs(self.ellipse_dir, exist_ok=True)

        self.counter = 0
        self.running = True

        self.worker = threading.Thread(
            target=self._worker_loop,
            daemon=True
        )
        self.worker.start()

        print(f"[SAVE] Session started: {self.ellipse_dir}")

    def stop_session(self):
        self.running = False
        self.enabled = False
        print("[SAVE] Session stopped")

    def set_enabled(self, state: bool):
        if state and not self.enabled:
            self.enabled = True
            self.start_session()
        elif not state and self.enabled:
            self.enabled = False
            self.stop_session()

    # =========================
    # PUBLIC API (FAST)
    # =========================
    def save(self, img_bgr):
        if not self.enabled:
            return

        print("[SAVE] enqueue", type(img_bgr), getattr(img_bgr, "shape", None))

        try:
            self.queue.put_nowait(img_bgr)
        except Exception:
            # queue full → drop frame, but NEVER block GUI
            pass

    # =========================
    # BACKGROUND WORKER
    # =========================
    def _worker_loop(self):
        while self.running:
            try:
                img = self.queue.get(timeout=0.2)
            except Exception:
                continue

            # ===== HARD VALIDATION =====
            if img is None:
                self.queue.task_done()
                continue

            if not hasattr(img, "shape"):
                print("[SAVE][WARN] Dropped non-image:", type(img))
                self.queue.task_done()
                continue

            if img.size == 0:
                print("[SAVE][WARN] Dropped empty image")
                self.queue.task_done()
                continue

            self.counter += 1

            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"ellipse_{ts}_{self.counter:05d}.png"
            path = os.path.join(self.ellipse_dir, filename)

            ok = cv2.imwrite(path, img)
            if not ok:
                print("[SAVE][ERROR] imwrite failed:", path)
            else:
                print("[SAVE] PNG saved:", path)

            self.queue.task_done()