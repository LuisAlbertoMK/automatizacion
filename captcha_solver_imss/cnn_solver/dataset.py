"""
dataset.py
Build dataset from labeled captcha images: segment → char images → augment.

Each captcha is 7 alphanumeric chars. We segment via vertical projection.
Output: (32, 32) grayscale char images with class labels (0-35).
"""
import os
import random
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

# ── Character mapping ────────────────────────────────────────────────
# 36 classes: A-Z (0-25), 0-9 (26-35)
CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
CHAR_TO_IDX = {c: i for i, c in enumerate(CHARS)}
IDX_TO_CHAR = {i: c for i, c in enumerate(CHARS)}
N_CLASSES = 36

# ── Paths ────────────────────────────────────────────────────────────
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "test_samples"
MODEL_DIR = Path(__file__).resolve().parent / "models"


def segment_captcha(
    img: np.ndarray, expected_len: int = 7, debug: bool = False
) -> List[np.ndarray]:
    """
    Segment a captcha image into individual character images.
    Uses inverted Otsu binary + vertical projection profiling.

    Args:
        img: (H, W, 3) BGR image
        expected_len: expected number of characters (default 7)
        debug: if True, return debug info

    Returns:
        List of (h_ch, w_ch) grayscale char images (not resized)
    """
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    h, w = gray.shape

    # Otsu threshold → inverted binary (white text on black)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Vertical projection: count white pixels per column
    v_proj = np.sum(binary, axis=0) / 255.0
    max_proj = np.max(v_proj) if np.max(v_proj) > 0 else 1.0
    v_proj_norm = v_proj / max_proj

    # Find gaps between characters (columns with <10% activity)
    gap_threshold = 0.1
    in_gap = False
    segments = []
    prev_end = 0

    for col in range(w):
        is_active = v_proj_norm[col] >= gap_threshold
        if is_active and in_gap:
            # End of gap
            gap_end = col
            # Only count if gap is meaningful (>=2px) and segment before has >=3px
            if gap_end - gap_start >= 2 and gap_start - prev_end >= 3:
                segments.append((prev_end, gap_start))
                prev_end = gap_end
            in_gap = False
        elif not is_active and not in_gap:
            gap_start = col
            in_gap = True

    # Last segment
    if w - prev_end >= 3:
        segments.append((prev_end, w))

    # If we don't have expected_len segments, fall back to equal-width split
    if len(segments) != expected_len:
        seg_w = w // expected_len
        segments = [(i * seg_w, (i + 1) * seg_w) for i in range(expected_len)]

    # Extract char images with bounding box optimization
    chars = []
    for start, end in segments:
        char_roi = binary[:, start:end]
        # Find actual bounding box (trim whitespace)
        cols = np.any(char_roi, axis=0)
        rows = np.any(char_roi, axis=1)
        if not np.any(cols) or not np.any(rows):
            chars.append(np.zeros((h, end - start), dtype=np.uint8))
            continue
        x1, x2 = np.where(cols)[0][[0, -1]]
        y1, y2 = np.where(rows)[0][[0, -1]]
        # Add 1px padding
        y1, y2 = max(0, y1 - 1), min(h, y2 + 2)
        x1, x2 = max(0, x1 - 1), min(char_roi.shape[1], x2 + 2)
        char_img = char_roi[y1:y2, x1:x2]
        chars.append(char_img)

    return chars


def normalize_char(char_img: np.ndarray, target_size: int = 32) -> np.ndarray:
    """
    Resize a char image to (target_size, target_size) with aspect ratio preservation.
    Pads with zeros (black) to fill remaining space.
    """
    h, w = char_img.shape
    # Determine scale to fit within target_size
    scale = min(target_size / max(h, 1), target_size / max(w, 1))
    new_h, new_w = max(1, int(h * scale)), max(1, int(w * scale))

    resized = cv2.resize(char_img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    # Center in target_size x target_size
    canvas = np.zeros((target_size, target_size), dtype=np.float32)
    y_off = (target_size - new_h) // 2
    x_off = (target_size - new_w) // 2
    canvas[y_off : y_off + new_h, x_off : x_off + new_w] = resized / 255.0

    return canvas.astype(np.float32).astype(np.float32)


def elastic_transform(img: np.ndarray, alpha: float = 12.0, sigma: float = 3.0) -> np.ndarray:
    """Apply elastic deformation (simulates captcha distortion)."""
    random_state = np.random.RandomState(random.randint(0, 1000))
    shape = img.shape
    dx = cv2.GaussianBlur(
        (random_state.rand(*shape) * 2 - 1), ksize=(3, 3), sigmaX=sigma
    ) * alpha
    dy = cv2.GaussianBlur(
        (random_state.rand(*shape) * 2 - 1), ksize=(3, 3), sigmaX=sigma
    ) * alpha

    x, y = np.meshgrid(np.arange(shape[1]), np.arange(shape[0]))
    mapx = (x + dx).astype(np.float32)
    mapy = (y + dy).astype(np.float32)
    return cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def cutout(img: np.ndarray, max_holes: int = 2, max_size: int = 6):
    """Randomly erase small patches (prevents overfitting to stroke patterns)."""
    h, w = img.shape[:2]
    result = img.copy()
    for _ in range(random.randint(0, max_holes)):
        ch = random.randint(2, max_size)
        cw = random.randint(2, max_size)
        x = random.randint(0, w - cw)
        y = random.randint(0, h - ch)
        result[y:y+ch, x:x+cw] = 0.0
    return result


def augment_char(img: np.ndarray) -> np.ndarray:
    """Apply HEAVY random augmentation to a (32, 32) char image."""
    # Elastic deformation (subtle — simulates captcha warping)
    if random.random() < 0.4:
        img = elastic_transform(img, alpha=random.uniform(5, 15), sigma=random.uniform(2, 4))

    # Rotation ±15°
    angle = random.uniform(-15, 15)
    M = cv2.getRotationMatrix2D((16, 16), angle, 1.0)
    img = cv2.warpAffine(img, M, (32, 32), borderValue=0.0)

    # Shift ±3px
    dx = random.uniform(-3, 3)
    dy = random.uniform(-3, 3)
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    img = cv2.warpAffine(img, M, (32, 32), borderValue=0.0)

    # Scale ±20%
    scale = random.uniform(0.80, 1.20)
    new_w = max(8, min(48, int(32 * scale)))
    new_h = max(8, min(48, int(32 * scale)))
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    canvas = np.zeros((32, 32), dtype=np.float32)
    x_off = (32 - new_w) // 2
    y_off = (32 - new_h) // 2
    if new_w > 32 or new_h > 32:
        cx1 = (new_w - 32) // 2
        cy1 = (new_h - 32) // 2
        resized = resized[cy1:cy1+32, cx1:cx1+32]
        canvas = resized[:32, :32]
    else:
        if x_off >= 0 and y_off >= 0:
            canvas[y_off:y_off+new_h, x_off:x_off+new_w] = resized
    img = canvas

    # Random brightness/contrast
    alpha = random.uniform(0.6, 1.4)
    beta = random.uniform(-0.15, 0.15)
    img = np.clip(img * alpha + beta, 0.0, 1.0)

    # Random noise
    if random.random() < 0.4:
        noise = np.random.randn(32, 32).astype(np.float32) * 0.05
        img = np.clip(img + noise, 0.0, 1.0)

    # Cutout (random erasing)
    if random.random() < 0.3:
        img = cutout(img)

    return img


def synthesize_missing_char(char_label: str) -> np.ndarray:
    """
    Generate a synthetic (32, 32) image for missing chars (I, O, Z, 0, 1, 9)
    by rendering with PIL + applying captcha-like noise.
    """
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("L", (32, 32), 0)  # Black background
    draw = ImageDraw.Draw(img)

    # Try to find a reasonable font
    font_paths = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\consola.ttf",
        r"C:\Windows\Fonts\cour.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ]
    font = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 22)
                break
            except Exception:
                continue

    # Draw character centered
    bbox = draw.textbbox((0, 0), char_label, font=font) if font else (0, 0, 16, 22)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (32 - tw) // 2 - bbox[0]
    y = (32 - th) // 2 - bbox[1] - 2
    draw.text((x, y), char_label, fill=255, font=font)

    char_img = np.array(img, dtype=np.float32) / 255.0

    # Apply captcha-like distortions
    # 1. Slight rotation
    angle = random.uniform(-8, 8)
    M = cv2.getRotationMatrix2D((16, 16), angle, 1.0)
    char_img = cv2.warpAffine(char_img, M, (32, 32), borderValue=0.0)

    # 2. Add noise
    noise = np.random.randn(32, 32).astype(np.float32) * 0.05
    char_img = np.clip(char_img + noise, 0.0, 1.0)

    # 3. Erosion/dilation for thickness variation
    if random.random() < 0.3:
        k = np.ones((2, 2), np.uint8)
        # Convert to uint8 for morphological ops
        img_u8 = (char_img * 255).astype(np.uint8)
        if random.random() < 0.5:
            img_u8 = cv2.erode(img_u8, k, iterations=1)
        else:
            img_u8 = cv2.dilate(img_u8, k, iterations=1)
        char_img = img_u8.astype(np.float32) / 255.0

    return char_img


# ── PyTorch Dataset ──────────────────────────────────────────────────

class CaptchaCharDataset:
    """
    Dataset of individual characters extracted from labeled captcha images.

    Each sample: (image_tensor, label_idx) where image is (1, 32, 32) float tensor.
    """
    def __init__(
        self,
        samples_dir: str = None,
        augment: bool = True,
        synthetic_per_class: int = 20,
        target_size: int = 32,
    ):
        self.samples_dir = Path(samples_dir or SAMPLES_DIR)
        self.augment = augment
        self.target_size = target_size
        self.synthetic_per_class = synthetic_per_class

        self.samples: List[Tuple[np.ndarray, int]] = []  # (char_image, label_idx)

        self._load_samples()
        self._add_synthetic_missing()

        print(f"  [CNN] Dataset: {len(self.samples)} char samples "
              f"({len(set(l for _, l in self.samples))}/{N_CLASSES} classes)")

    def _load_samples(self):
        """Extract chars from all labeled captcha images."""
        if not self.samples_dir.exists():
            raise FileNotFoundError(f"Samples dir not found: {self.samples_dir}")

        files = sorted([
            f for f in os.listdir(self.samples_dir)
            if f.endswith(('.jpg', '.PNG'))
        ])

        for fname in files:
            stem = Path(fname).stem
            # Expected label is the filename stem (may have _suffix)
            label = stem.split("_")[0].upper()

            # Validate all 7 chars are valid
            if len(label) != 7:
                continue
            if not all(c in CHAR_TO_IDX for c in label):
                continue

            path = self.samples_dir / fname
            img = cv2.imread(str(path))
            if img is None:
                continue

            # Segment into 7 chars
            chars = segment_captcha(img, expected_len=7)
            if len(chars) != 7:
                continue

            for char_img, expected_char in zip(chars, label):
                normalized = normalize_char(char_img, self.target_size)
                if normalized is None or normalized.shape != (self.target_size, self.target_size):
                    continue
                label_idx = CHAR_TO_IDX[expected_char]
                self.samples.append((normalized, label_idx))

    def _add_synthetic_missing(self):
        """Generate synthetic data for chars with no samples."""
        existing = set(l for _, l in self.samples)
        missing = [c for c, i in CHAR_TO_IDX.items() if i not in existing]
        if not missing:
            return

        random.seed(42)
        for c in missing:
            idx = CHAR_TO_IDX[c]
            for _ in range(self.synthetic_per_class):
                syn = synthesize_missing_char(c)
                # Apply standard augmentation
                if self.augment:
                    syn = augment_char(syn)
                # Ensure correct size
                if syn.shape != (self.target_size, self.target_size):
                    syn = cv2.resize(syn, (self.target_size, self.target_size))
                self.samples.append((syn, idx))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        import torch
        img, label = self.samples[idx]
        if self.augment:
            img = augment_char(img)
        tensor = torch.from_numpy(img).float().unsqueeze(0)
        return tensor, label


def get_dataloaders(
    batch_size: int = 32,
    val_split: float = 0.15,
    augment: bool = True,
    synthetic_per_class: int = 30,
):
    """
    Create train/val dataloaders.

    Returns:
        (train_loader, val_loader, n_classes)
    """
    import torch
    from torch.utils.data import DataLoader
    dataset = CaptchaCharDataset(
        augment=augment,
        synthetic_per_class=synthetic_per_class,
    )

    n = len(dataset)
    n_val = max(1, int(n * val_split))
    n_train = n - n_val

    # Stratified split by class
    from collections import defaultdict
    class_indices = defaultdict(list)
    for i, (_, label) in enumerate(dataset.samples):
        class_indices[label].append(i)

    train_indices = set()
    val_indices = set()
    for label, indices in class_indices.items():
        random.shuffle(indices)
        n_label_val = max(1, int(len(indices) * val_split))
        for i in indices[:n_label_val]:
            val_indices.add(i)
        for i in indices[n_label_val:]:
            train_indices.add(i)

    train_indices = sorted(train_indices)
    val_indices = sorted(val_indices)

    train_subset = torch.utils.data.Subset(dataset, train_indices)
    val_subset = torch.utils.data.Subset(dataset, val_indices)

    train_loader = DataLoader(train_subset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_subset, batch_size=batch_size, shuffle=False)

    return train_loader, val_loader, N_CLASSES
