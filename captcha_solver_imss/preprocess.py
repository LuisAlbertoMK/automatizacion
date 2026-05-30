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

import cv2
import numpy as np
from typing import Optional
from pathlib import Path


UPSCALE_FACTOR = 4  # 220×40 → 880×160


def preprocess_pipeline(img_array: np.ndarray) -> dict:
    """
    Variantes para EasyOCR (BGR, 3 canales, sin binarizar).

    Retorna dict con:
      - "raw":           solo upscale + sharpening
      - "clahe":         CLAHE + upscale (mejor contraste local)
      - "grayscale_bgr": grayscale → 3ch + upscale
      - "denoised":      denoise suave + upscale
    """
    variants = {}

    # 1. RAW — solo upscale (mínimo procesamiento)
    h, w = img_array.shape[:2]
    raw = cv2.resize(
        img_array,
        (w * UPSCALE_FACTOR, h * UPSCALE_FACTOR),
        interpolation=cv2.INTER_LANCZOS4,
    )
    # Sharpening suave
    raw = _sharpen(raw)
    variants["raw"] = raw

    # 2. CLAHE — mejora contraste local (ideal para texto con fondo ruidoso)
    lab = cv2.cvtColor(raw, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    l_enhanced = clahe.apply(l)
    lab_enhanced = cv2.merge([l_enhanced, a, b])
    clahe_bgr = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
    variants["clahe"] = clahe_bgr

    # 3. GRAYSCALE — a grises y de vuelta a BGR (elimina ruido de color)
    gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
    gray_3ch = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    variants["gray"] = gray_3ch

    # 4. DENOISED — denoise suave bilateral (preserva bordes)
    denoised = cv2.bilateralFilter(raw, 7, 50, 50)
    variants["denoised"] = denoised

    # 5. GRAY + CLAHE — grises + mejora de contraste
    gray_clahe = clahe.apply(gray)
    gray_clahe_bgr = cv2.cvtColor(gray_clahe, cv2.COLOR_GRAY2BGR)
    variants["gray_clahe"] = gray_clahe_bgr

    # 6. MORPH GRADIENT — enfatiza bordes (ayuda con 'r', 'l', 'i' angostos)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
    grad_bgr = cv2.cvtColor(grad, cv2.COLOR_GRAY2BGR)
    variants["gradient"] = grad_bgr

    return variants


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
