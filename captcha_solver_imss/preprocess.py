"""
preprocess.py
Pipeline de preprocessing OpenCV para CAPTCHA del IMSS (CaptchaServlet).

Basado en análisis de 11 imágenes reales del portal IMSS:
  - Tamaño: ~220×40 px JPEG
  - Caracteres alfanuméricos (A-Z + 0-9), fondo con ruido/textura
  - Casos mixtos (upper + lower), 7 caracteres típicamente

Lección aprendida: BINARIZAR DESTRUYE LOS CARACTERES.
Este CAPTCHA tiene ruido que el threshold no separa bien.
Solución: NO binarizar. Mejorar contraste con CLAHE, upscale limpio.
"""

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

UPSCALE_FACTOR = 4  # 220×40 → 880×160


def _upscale(img: np.ndarray) -> np.ndarray:
    """Upscale 4x con LANCZOS."""
    h, w = img.shape[:2]
    return cv2.resize(img, (w * UPSCALE_FACTOR, h * UPSCALE_FACTOR),
                      interpolation=cv2.INTER_LANCZOS4)


def generate_variants(image: np.ndarray):
    """
    Yield preprocessing variants lazily — stop when caller breaks early.

    Yields (name, variant_image) pairs ordered by expected usefulness.
    """
    raw = _upscale(image)
    raw = _sharpen(raw)
    yield "raw", raw

    gray_raw = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
    gray_3ch = cv2.cvtColor(gray_raw, cv2.COLOR_GRAY2BGR)
    yield "gray", gray_3ch

    denoised = cv2.bilateralFilter(raw, 7, 50, 50)
    yield "denoised", denoised

    grad_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    grad = cv2.morphologyEx(gray_raw, cv2.MORPH_GRADIENT, grad_kernel)
    grad_bgr = cv2.cvtColor(grad, cv2.COLOR_GRAY2BGR)
    yield "gradient", grad_bgr

    lab = cv2.cvtColor(raw, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    l_enhanced = clahe.apply(l)
    lab_enhanced = cv2.merge([l_enhanced, a, b])
    clahe_bgr = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
    yield "clahe", clahe_bgr

    gray_clahe = clahe.apply(gray_raw)
    gray_clahe_bgr = cv2.cvtColor(gray_clahe, cv2.COLOR_GRAY2BGR)
    yield "gray_clahe", gray_clahe_bgr


def preprocess_pipeline(img_array: np.ndarray) -> dict:
    """Eager wrapper: returns full dict for callers that need it."""
    return {name: img for name, img in generate_variants(img_array)}


def _sharpen(img: np.ndarray, strength: float = 0.3) -> np.ndarray:
    """Sharpening kernel suave (no satura)."""
    kernel = np.array([
        [-strength, -strength, -strength],
        [-strength, 1 + 8*strength, -strength],
        [-strength, -strength, -strength],
    ])
    return cv2.filter2D(img, -1, kernel)


def load_image(source) -> Optional[np.ndarray]:
    """Carga imagen desde bytes, path o array."""
    if isinstance(source, np.ndarray):
        return source
    if isinstance(source, bytes):
        arr = np.frombuffer(source, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    p = Path(source) if isinstance(source, str) else source
    if isinstance(p, Path) and p.exists():
        return cv2.imread(str(p))
    return None


def save_variants(variants: dict, prefix: str = "preview", output_dir: Optional[Path] = None):
    """Guarda variantes como PNG para debug."""
    out = Path(output_dir or ".")
    out.mkdir(parents=True, exist_ok=True)
    for name, img in variants.items():
        cv2.imwrite(str(out / f"{prefix}_{name}.png"), img)
