#!/usr/bin/env python3
"""
generate_dataset.py — Pipeline de dataset sintético para captcha IMSS.
Genera variaciones aumentadas de captchas reales para mejorar el CNN.

Uso:
    python tools/generate_dataset.py                          # Generar dataset aumentado
    python tools/generate_dataset.py --auto-label             # Auto-etiquetar con ensemble
    python tools/generate_dataset.py --download 100           # Descargar N captchas nuevos
"""

import argparse
import random
from pathlib import Path

import cv2
import numpy as np

# ── Rutas ──────────────────────────────────────────────────
CAPTCHA_DIR = Path(__file__).parent.parent / "captcha_solver_imss" / "raw_captchas"
MODEL_DIR = Path(__file__).parent.parent / "captcha_solver_imss" / "cnn_solver" / "models"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "synthetic"


# ── Augmentations ──────────────────────────────────────────

def augment_rotation(img: np.ndarray, max_angle: float = 5) -> np.ndarray:
    """Rotación leve (±max_angle grados)."""
    h, w = img.shape[:2]
    angle = random.uniform(-max_angle, max_angle)
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)


def augment_noise(img: np.ndarray, intensity: float = 0.02) -> np.ndarray:
    """Ruido sal y pimienta."""
    noise = np.random.rand(*img.shape) < intensity
    salt = np.random.rand(*img.shape) < intensity / 2
    result = img.copy()
    result[noise] = 0
    result[salt] = 255
    return result


def augment_blur(img: np.ndarray, ksize: int = 3) -> np.ndarray:
    """Desenfoque gaussiano leve."""
    if ksize % 2 == 0:
        ksize += 1
    return cv2.GaussianBlur(img, (ksize, ksize), 0)


def augment_contrast(img: np.ndarray, factor_range=(0.8, 1.5)) -> np.ndarray:
    """Variación de contraste."""
    factor = random.uniform(*factor_range)
    return cv2.convertScaleAbs(img, alpha=factor, beta=0)


def augment_warp(img: np.ndarray, shift: int = 2) -> np.ndarray:
    """Distorsión de perspectiva leve."""
    h, w = img.shape[:2]
    src_pts = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
    dst_pts = np.float32([
        [random.uniform(-shift, shift), random.uniform(-shift, shift)],
        [w + random.uniform(-shift, shift), random.uniform(-shift, shift)],
        [random.uniform(-shift, shift), h + random.uniform(-shift, shift)],
        [w + random.uniform(-shift, shift), h + random.uniform(-shift, shift)],
    ])
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    return cv2.warpPerspective(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)


AUGMENTATIONS = [
    ("rotated", augment_rotation),
    ("noise", augment_noise),
    ("blurred", augment_blur),
    ("contrast", augment_contrast),
    ("warped", augment_warp),
]


def augment_image(img: np.ndarray, copies: int = 5) -> list:
    """Genera N variaciones aumentadas de una imagen."""
    results = []
    for _ in range(copies):
        aug = img.copy()
        # Aplicar 2-3 augmentations aleatorias
        selected = random.sample(AUGMENTATIONS, random.randint(2, 3))
        for name, func in selected:
            aug = func(aug)
        results.append(aug)
    return results


# ── Auto-labeling con ensemble ────────────────────────────

def auto_label(download_new: int = 0):
    """Auto-etiquetar captchas usando el ensemble de modelos existentes."""
    try:
        from captcha_solver_imss.solver import IMSCaptchaSolver
    except ImportError:
        print("  [ERROR] captcha_solver_imss no disponible. Instalá torch + opencv")
        return

    solver = IMSCaptchaSolver(verbose=False)

    if download_new > 0:
        print(f"  Descargando {download_new} captchas nuevos...")
        # TODO: Integrar con el downloader de captchas
        print("  Usá: python get_captcha.py --count N para descargar")

    captchas = list(CAPTCHA_DIR.glob("*.png")) + list(CAPTCHA_DIR.glob("*.jpg"))
    print(f"  {len(captchas)} captchas encontrados en {CAPTCHA_DIR}")

    labeled = 0
    for cap in captchas:
        img_bytes = cap.read_bytes()
        result = solver.solve(img_bytes)
        if result["success"] and result["score"] >= 0.8:
            # Guardar etiqueta
            label_path = cap.with_suffix(".txt")
            label_path.write_text(result["value"])
            labeled += 1
        else:
            # Baja confianza — mover a pendientes
            pending_dir = CAPTCHA_DIR / "_pending"
            pending_dir.mkdir(exist_ok=True)
            cap.rename(pending_dir / cap.name)

    print(f"  Auto-etiquetados: {labeled}/{len(captchas)}")
    print(f"  Pendientes (baja confianza): {len(captchas) - labeled}")


# ── Main ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pipeline de dataset sintético para captcha IMSS")
    parser.add_argument("--auto-label", action="store_true", help="Auto-etiquetar captchas con ensemble")
    parser.add_argument("--download", type=int, default=0, help="Descargar N captchas nuevos")
    parser.add_argument("--augment", action="store_true", help="Generar variaciones aumentadas")
    parser.add_argument("--copies", type=int, default=5, help="Copias por captcha (default: 5)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.auto_label or args.download:
        auto_label(download_new=args.download)

    if args.augment:
        captchas = list(CAPTCHA_DIR.glob("*.png")) + list(CAPTCHA_DIR.glob("*.jpg"))
        print(f"  Generando {args.copies}x augmentations para {len(captchas)} captchas...")

        total = 0
        for cap in captchas:
            img = cv2.imread(str(cap), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue

            augs = augment_image(img, copies=args.copies)
            for i, aug in enumerate(augs):
                stem = cap.stem
                out_path = OUTPUT_DIR / f"{stem}_aug_{i}.png"
                cv2.imwrite(str(out_path), aug)
                total += 1

        print(f"  Generados {total} captchas sintéticos en {OUTPUT_DIR}")

    if not any([args.auto_label, args.download, args.augment]):
        parser.print_help()


if __name__ == "__main__":
    main()
