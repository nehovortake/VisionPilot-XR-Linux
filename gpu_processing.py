"""
GPU-accelerated image processing using PyTorch CUDA.
Falls back to CPU if CUDA is not available.

Optimized for real-time processing with hybrid CPU/GPU approach.
Uses OpenCV for color conversions (highly optimized C++),
and PyTorch for parallel array operations where beneficial.
"""
import cv2
import numpy as np

# Check PyTorch CUDA availability
TORCH_CUDA_AVAILABLE = False
torch = None

try:
    import torch
    TORCH_CUDA_AVAILABLE = torch.cuda.is_available()
    if TORCH_CUDA_AVAILABLE:
        print(f"[GPU Processing] PyTorch CUDA Available: True")
        try:
            device_name = torch.cuda.get_device_name(0)
        except Exception:
            device_name = "Unknown GPU"
        print(f"[GPU Processing] CUDA Device: {device_name}")
        print(f"[GPU Processing] CUDA Version: {torch.version.cuda}")
        # Warmup GPU
        _ = torch.zeros(1, device='cuda')
    else:
        print("[GPU Processing] PyTorch installed but CUDA not available")
except ImportError:
    print("[GPU Processing] PyTorch not installed")
except Exception as e:
    print(f"[GPU Processing] PyTorch CUDA error: {e}")

CUDA_AVAILABLE = TORCH_CUDA_AVAILABLE
print(f"[GPU Processing] GPU Acceleration: {'ENABLED' if CUDA_AVAILABLE else 'DISABLED'}")


class GPUProcessor:
    """GPU-accelerated image processor with CPU fallback.

    Uses hybrid approach for optimal performance:
    - OpenCV for color conversions (optimized C++)
    - PyTorch CUDA for Sobel/edge detection
    """

    def __init__(self):
        self.use_gpu = TORCH_CUDA_AVAILABLE
        self.device = None

        if self.use_gpu and torch is not None:
            self.device = torch.device("cuda")
            # Pre-allocate Sobel kernels on GPU
            self._sobel_x = torch.tensor(
                [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]],
                dtype=torch.float32, device=self.device
            ).view(1, 1, 3, 3)
            self._sobel_y = torch.tensor(
                [[-1, -2, -1], [0, 0, 0], [1, 2, 1]],
                dtype=torch.float32, device=self.device
            ).view(1, 1, 3, 3)
            print("[GPU Processing] GPUProcessor initialized with PyTorch CUDA")
        else:
            print("[GPU Processing] GPUProcessor using CPU fallback")

    # =========================================================
    # RED NULLING - OpenCV (original version)
    # =========================================================
    def red_nulling_gpu(self, frame: np.ndarray, rd: float = 1.5, min_brightness: int = 40) -> np.ndarray:
        """
        Red nulling: keep only pixels where Red channel dominates.
        Every pixel where R < rd*G or R < rd*B is set to black (nulled).

        This shows skin (which has red tones) but ellipse detection filters non-circular shapes.
        """
        try:
            if frame is None or frame.size == 0:
                return frame

            # Extract channels
            b = frame[:, :, 0].astype(np.float32)
            g = frame[:, :, 1].astype(np.float32)
            r = frame[:, :, 2].astype(np.float32)

            # Red dominant mask: R must be >= rd * G and >= rd * B
            mask = ((r >= rd * g) & (r >= rd * b)).astype(np.uint8) * 255

            # Brightness gating (exclude very dark pixels)
            if min_brightness > 0:
                bright_mask = (r >= min_brightness).astype(np.uint8) * 255
                mask = cv2.bitwise_and(mask, bright_mask)

            # Light morphological cleanup (removes tiny noise)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

            # Apply mask to original image
            result = cv2.bitwise_and(frame, frame, mask=mask)
            return result

        except Exception as e:
            print(f"[GPU] Red nulling error: {e}")
            return frame


    # =========================================================
    # CANNY EDGE DETECTION - OpenCV (fastest)
    # =========================================================
    def canny_gpu(self, frame: np.ndarray, t1: int = 80, t2: int = 150, sigma: float = 1.0) -> np.ndarray:
        """
        Fast Canny edge detection using OpenCV.
        OpenCV Canny is highly optimized C++ with SIMD - faster than PyTorch GPU for this.
        GPU transfer overhead makes PyTorch slower for simple operations like this.
        """
        try:
            if frame is None or frame.size == 0:
                return frame

            # Convert to grayscale
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            # Gaussian blur (OpenCV is highly optimized)
            ksize = max(3, int(sigma * 4) | 1)
            blurred = cv2.GaussianBlur(gray, (ksize, ksize), sigma)

            # OpenCV Canny - highly optimized C++ implementation
            edges = cv2.Canny(blurred, t1, t2)

            return edges

        except Exception as e:
            print(f"[Canny] Error: {e}")
            return self.canny_cpu(frame, t1, t2, sigma)

    def canny_cpu(self, frame: np.ndarray, t1: int = 80, t2: int = 150, sigma: float = 1.0) -> np.ndarray:
        """CPU fallback for Canny using OpenCV."""
        try:
            from image_processing import apply_canny
            return apply_canny(frame, t1, t2, sigma)
        except Exception:
            # Ultimate fallback
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            blurred = cv2.GaussianBlur(gray, (5, 5), 1.0)
            return cv2.Canny(blurred, t1, t2)

    # =========================================================
    # GAUSSIAN BLUR - OpenCV (already optimized)
    # =========================================================
    def gaussian_blur_gpu(self, frame: np.ndarray, ksize: int = 5, sigma: float = 1.0) -> np.ndarray:
        """Gaussian blur using OpenCV (already highly optimized with SIMD)."""
        return cv2.GaussianBlur(frame, (ksize, ksize), sigma)


# Global GPU processor instance
_gpu_processor = None

def get_gpu_processor() -> GPUProcessor:
    """Get or create the global GPU processor instance."""
    global _gpu_processor
    if _gpu_processor is None:
        _gpu_processor = GPUProcessor()
    return _gpu_processor


# =========================================================
# CONVENIENCE FUNCTIONS
# =========================================================
def red_nulling(frame: np.ndarray, rd: float = 1.5, min_brightness: int = 40) -> np.ndarray:
    """Red nulling with automatic GPU/CPU selection."""
    return get_gpu_processor().red_nulling_gpu(frame, rd, min_brightness)

def canny_edges(frame: np.ndarray, t1: int = 80, t2: int = 150, sigma: float = 1.0) -> np.ndarray:
    """Canny edge detection with automatic GPU/CPU selection."""
    return get_gpu_processor().canny_gpu(frame, t1, t2, sigma)

def gaussian_blur(frame: np.ndarray, ksize: int = 5, sigma: float = 1.0) -> np.ndarray:
    """Gaussian blur with automatic GPU/CPU selection."""
    return get_gpu_processor().gaussian_blur_gpu(frame, ksize, sigma)

def is_gpu_available() -> bool:
    """Check if GPU processing is available."""
    return TORCH_CUDA_AVAILABLE

