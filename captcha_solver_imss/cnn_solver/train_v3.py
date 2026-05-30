"""
train_v3.py
Entrenamiento mejorado para CNN captcha IMSS (62 clases, mixed case).

Mejoras vs train_v2:
  - Soporte para 3 arquitecturas (WideCNN, ResidualCNN, AttentionCNN)
  - Augmentación realista: elastic deformation, width stretch, noise
  - Validación a nivel CAPTCHA (no mezclar chars del mismo captcha entre train/val)
  - Temprano stopping por validación
  - Balanced sampler para clases con pocos datos
  - Checkpoint del mejor modelo por val_acc (no train_acc)
  - Soporte para entrenar ensemble (N seeds)
  - Label smoothing opcional (funciona con más datos)

Uso:
    py -3.14 -m captcha_solver_imss.cnn_solver.train_v3
    py -3.14 -m captcha_solver_imss.cnn_solver.train_v3 --arch wide
    py -3.14 -m captcha_solver_imss.cnn_solver.train_v3 --ensemble 3
"""
import argparse
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

from .model_v2 import create_model, count_params
from .train_v2 import segment_captcha, normalize_char, CHAR_TO_IDX, IDX_TO_CHAR, N_CLASSES, MODEL_DIR, SAMPLES_DIR


# ═══════════════════════════════════════════════════════════════════════════
# Augmentation (realista para captcha IMSS)
# ═══════════════════════════════════════════════════════════════════════════

def _elastic_deform(img, alpha=15, sigma=3):
    """Elastic deformation — simula la distorsión de la fuente IMSS."""
    h, w = img.shape
    dx = np.random.randn(h, w) * alpha
    dy = np.random.randn(h, w) * alpha

    # Suavizar con Gaussian
    from scipy.ndimage import gaussian_filter
    dx = gaussian_filter(dx, sigma=sigma)
    dy = gaussian_filter(dy, sigma=sigma)

    x, y = np.meshgrid(np.arange(w), np.arange(h))
    map_x = (x + dx).astype(np.float32)
    map_y = (y + dy).astype(np.float32)

    return cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR, borderValue=0.0)


def _width_warp(img, stretch=0.15):
    """Stretch/compress horizontalmente (la fuente IMSS varía ancho de caracteres)."""
    h, w = img.shape
    factor = 1.0 + random.uniform(-stretch, stretch)
    nw = max(4, int(w * factor))
    stretched = cv2.resize(img, (nw, h), interpolation=cv2.INTER_LINEAR)
    if nw >= w:
        return cv2.resize(stretched, (w, h), interpolation=cv2.INTER_AREA)
    else:
        # Center the stretched image
        canvas = np.zeros((h, w), dtype=np.float32)
        x_off = (w - nw) // 2
        canvas[:, x_off:x_off+nw] = stretched
        return canvas


def augment_char(img: np.ndarray, intensity: float = 1.0) -> np.ndarray:
    """
    Augmentación realista para caracteres de captcha IMSS.

    Args:
        img: (32, 32) float32 array, values in [0, 1]
        intensity: 0.0 = no augmentation, 1.0 = full augmentation

    Returns:
        Augmented (32, 32) float32 array
    """
    aug = img.copy()

    if intensity <= 0:
        return aug

    r = random.random

    # 1. Elastic deformation (simula distorsión de fuente)
    if r() < 0.4 * intensity:
        aug = _elastic_deform(aug, alpha=random.uniform(5, 15), sigma=random.uniform(2, 4))

    # 2. Width stretch (la fuente IMSS es variable-width)
    if r() < 0.3 * intensity:
        aug = _width_warp(aug, stretch=0.12 * intensity)

    # 3. Small rotation
    if r() < 0.5 * intensity:
        angle = random.uniform(-4, 4) * intensity
        M = cv2.getRotationMatrix2D((16, 16), angle, 1.0)
        aug = cv2.warpAffine(aug, M, (32, 32), borderValue=0.0)

    # 4. Small shift
    if r() < 0.3 * intensity:
        dx = random.uniform(-1.5, 1.5) * intensity
        dy = random.uniform(-1, 1) * intensity
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        aug = cv2.warpAffine(aug, M, (32, 32), borderValue=0.0)

    # 5. Gaussian noise (simula compresión JPG)
    if r() < 0.2 * intensity:
        noise = np.random.randn(32, 32).astype(np.float32) * 0.03 * intensity
        aug = np.clip(aug + noise, 0, 1)

    # 6. Gaussian blur (simula captcha motion blur)
    if r() < 0.15 * intensity:
        ksize = random.choice([(3, 3), (5, 1), (1, 5)])
        aug = cv2.GaussianBlur(aug, ksize, 0)

    # 7. Erosion/Dilation (simula variación de grosor de línea)
    if r() < 0.1 * intensity:
        kernel = np.ones((2, 2), np.uint8)
        if r() < 0.5:
            aug = cv2.erode(aug, kernel, iterations=1)
        else:
            aug = cv2.dilate(aug, kernel, iterations=1)

    return np.clip(aug, 0, 1)


# ═══════════════════════════════════════════════════════════════════════════
# Data loading con split captcha-level
# ═══════════════════════════════════════════════════════════════════════════

def load_splits(val_ratio: float = 0.15, augment_intensity: float = 0.0,
                aug_mult: int = 1, raw_dir: Path = None):
    """
    Carga datos con split a nivel CAPTCHA (no mezclar chars del mismo captcha).

    Returns:
        train_data: [(char_img, label_idx), ...]
        val_data: [(char_img, label_idx), ...]
    """
    source_dirs = []
    if raw_dir and raw_dir.exists():
        source_dirs.append(raw_dir)
    if SAMPLES_DIR.exists():
        source_dirs.append(SAMPLES_DIR)

    if not source_dirs:
        print("  [CNN] ERROR: No se encontraron directorios con imágenes")
        print(f"  [CNN] Buscados: {SAMPLES_DIR} o {raw_dir}")
        return [], []

    # Cargar todas las imágenes con sus labels
    captchas = []  # [(img_path, label), ...]
    for sdir in source_dirs:
        for fname in sorted(os.listdir(sdir)):
            if not fname.endswith(('.jpg', '.PNG', '.png', '.jpeg')):
                continue
            stem = Path(fname).stem

            # El label puede ser: VALOR_UUID  o  VALOR
            parts = stem.split('_')
            label = parts[0]

            if len(label) != 7:
                continue
            if not all(c in CHAR_TO_IDX for c in label):
                continue

            captchas.append((sdir / fname, label))

    if not captchas:
        print("  [CNN] No se encontraron captchas válidos")
        return [], []

    print(f"  [CNN] Captchas totales: {len(captchas)}")

    # Split aleatorio a nivel captcha
    random.shuffle(captchas)
    n_val = max(0, min(int(len(captchas) * val_ratio), len(captchas) - 1))

    # Stratified split: asegurar que el validation set tenga representación
    # de todas las clases (ordenar por label diversidad)
    val_set = captchas[:n_val]
    train_set = captchas[n_val:]

    print(f"  [CNN] Train captchas: {len(train_set)}, Val captchas: {len(val_set)}")

    # Procesar
    train_data = _process_captchas(train_set, "train", augment_intensity, aug_mult)
    val_data = _process_captchas(val_set, "val", augment_intensity=0.0, aug_mult=1)

    return train_data, val_data


def _process_captchas(captchas, split_name, augment_intensity, aug_mult):
    """Procesa lista de captchas → samples de chars individuales."""
    samples = []
    class_counts = Counter()
    errors = 0

    for img_path, label in captchas:
        img = cv2.imread(str(img_path))
        if img is None:
            errors += 1
            continue

        chars = segment_captcha(img)
        if len(chars) != 7:
            errors += 1
            continue

        for ci, expected_char in zip(chars, label):
            norm = normalize_char(ci)
            label_idx = CHAR_TO_IDX[expected_char]
            samples.append((norm, label_idx))
            class_counts[label_idx] += 1

            # Augmentación on-the-fly: generar copias augmentadas
            if augment_intensity > 0 and aug_mult > 1:
                for _ in range(aug_mult - 1):
                    aug_norm = augment_char(norm.copy(), intensity=augment_intensity)
                    samples.append((aug_norm, label_idx))
                    class_counts[label_idx] += 1

    if errors:
        print(f"  [CNN] {split_name}: {len(samples)} chars, {errors} errores de segmentación")

    # Print class distribution
    n_classes = len(class_counts)
    min_count = min(class_counts.values()) if class_counts else 0
    max_count = max(class_counts.values()) if class_counts else 0
    print(f"  [CNN] {split_name}: {len(samples)} chars, "
          f"{n_classes}/{N_CLASSES} clases, "
          f"min={min_count}, max={max_count}")

    return samples


# ═══════════════════════════════════════════════════════════════════════════
# Balanced sampler
# ═══════════════════════════════════════════════════════════════════════════

def make_balanced_loader(samples, batch_size: int = 64, shuffle: bool = True):
    """
    Crea DataLoader con WeightedRandomSampler para balancear clases.
    """
    imgs = np.array([s[0] for s in samples], dtype=np.float32)
    labels = np.array([s[1] for s in samples], dtype=np.int64)

    # Calcular pesos por clase (inversamente proporcional a frecuencia)
    label_counts = Counter(labels)
    weights = [1.0 / label_counts[l] for l in labels]
    sample_weights = torch.DoubleTensor(weights)

    sampler = torch.utils.data.WeightedRandomSampler(
        sample_weights, num_samples=len(samples), replacement=True
    )

    imgs_t = torch.FloatTensor(np.expand_dims(imgs, 1))
    lbls_t = torch.LongTensor(labels)

    dataset = torch.utils.data.TensorDataset(imgs_t, lbls_t)

    loader = torch.utils.data.DataLoader(
        dataset, batch_size=batch_size,
        sampler=sampler if shuffle else None,
        shuffle=False if sampler else shuffle,
    )

    return loader


# ═══════════════════════════════════════════════════════════════════════════
# Evaluation
# ═══════════════════════════════════════════════════════════════════════════

@torch.no_grad()
def evaluate_captchas(model, device, verbose=True, raw_dir=None):
    """Evalúa a nivel captcha (accuracy exacta)."""
    model.eval()

    # Buscar imágenes
    source_dirs = []
    if raw_dir and raw_dir.exists():
        source_dirs.append(raw_dir)
    if SAMPLES_DIR.exists():
        source_dirs.append(SAMPLES_DIR)

    files = []
    for sdir in source_dirs:
        for f in os.listdir(sdir):
            if f.endswith(('.jpg', '.PNG', '.png', '.jpeg')):
                stem = Path(f).stem
                label = stem.split('_')[0]
                if len(label) == 7 and all(c in CHAR_TO_IDX for c in label):
                    files.append((sdir / f, label))

    files.sort(key=lambda x: x[0].name)

    correct, total = 0, 0
    errors = []
    char_correct, char_total = 0, 0

    for img_path, expected in files:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        chars = segment_captcha(img)
        if len(chars) != 7:
            continue

        predicted = ""
        for ci in chars:
            norm = normalize_char(ci)
            t = torch.from_numpy(norm).float().unsqueeze(0).unsqueeze(0).to(device)
            o = model(t)
            _, p = o.max(1)
            predicted += IDX_TO_CHAR[p.item()]

        # Char-level accuracy
        for a, b in zip(predicted, expected):
            if a == b:
                char_correct += 1
            char_total += 1

        # Captcha-level accuracy
        if predicted == expected:
            correct += 1
        else:
            errors.append((img_path.name, expected, predicted))
        total += 1

    captcha_acc = correct / total * 100 if total else 0
    char_acc = char_correct / char_total * 100 if char_total else 0

    if verbose:
        print(f"  [CNN] Captcha: {correct}/{total} = {captcha_acc:.1f}%")
        print(f"  [CNN] Char-level: {char_correct}/{char_total} = {char_acc:.1f}%")
        if errors:
            print(f"  [CNN] Errors ({len(errors)}):")
            for f, e, p in errors[:10]:
                diffs = ''.join('^' if a != b else ' ' for a, b in zip(e, p))
                print(f"    {f}: exp={e} got={p}")
                print(f"           {diffs}")

    return captcha_acc, char_acc, errors


# ═══════════════════════════════════════════════════════════════════════════
# Training
# ═══════════════════════════════════════════════════════════════════════════

def train_single(arch: str, seed: int = 42, epochs_p1: int = 200,
                 epochs_p2: int = 100, val_ratio: float = 0.15,
                 augment_intensity: float = 0.6, aug_mult: int = 3,
                 label_smoothing: float = 0.0, lr: float = 0.003,
                 raw_dir: Path = None, suffix: str = ""):
    """
    Entrena un único modelo.

    Args:
        arch: arquitectura ("wide", "residual", "attention")
        seed: random seed
        epochs_p1: épocas fase 1 (clean)
        epochs_p2: épocas fase 2 (augmented)
        val_ratio: fracción para validación
        augment_intensity: intensidad de augmentación (0-1)
        aug_mult: multiplicador de augmentación (1 = sin augment)
        label_smoothing: smoothing (0 = sin, >0 útil con más datos)
        raw_dir: directorio con imágenes crudas (raw_captchas/)
        suffix: sufijo para nombre del checkpoint
    """
    # ── Setup ──────────────────────────────────────────────────
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    device = torch.device("cpu")
    print(f"\n{'='*60}")
    print(f"  Model: {arch.upper()} | Seed: {seed}")
    print(f"  Device: {device}")
    print(f"  Classes: {N_CLASSES}")
    print(f"{'='*60}")

    # ── Data ───────────────────────────────────────────────────
    print(f"\n  === Loading data ===")
    train_samples, val_samples = load_splits(
        val_ratio=val_ratio, augment_intensity=0.0, aug_mult=1,
        raw_dir=raw_dir,
    )

    if not train_samples:
        print("  ERROR: No training data")
        return 0.0, None

    # ── Model ──────────────────────────────────────────────────
    model = create_model(arch, num_classes=N_CLASSES).to(device)
    print(f"  Params: {count_params(model):,}")

    criterion = nn.CrossEntropyLoss(label_smoothing=label_smoothing)

    # Checkpoint path
    if suffix:
        suffix = f"_{suffix}"
    best_path = MODEL_DIR / f"{arch}_s{seed}{suffix}.pt"

    best_val_acc = 0.0
    start = time.time()

    # ══════════════════════════════════════════════════════════
    # PHASE 1: Clean data
    # ══════════════════════════════════════════════════════════
    print(f"\n  === PHASE 1: Clean ({len(train_samples)} train, "
          f"{len(val_samples)} val) ===")

    train_loader = make_balanced_loader(train_samples, batch_size=64, shuffle=True)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=50, gamma=0.5)

    has_val = len(val_samples) > 0
    best_acc = 0.0
    best_metric = "val" if has_val else "train"
    patience = 30  # early stopping patience
    no_improve = 0

    for epoch in range(1, epochs_p1 + 1):
        model.train()
        t_loss, t_correct, t_total = 0.0, 0, 0

        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
            optimizer.step()

            t_loss += loss.item() * inputs.size(0)
            _, preds = outputs.max(1)
            t_total += targets.size(0)
            t_correct += preds.eq(targets).sum().item()

        scheduler.step()

        # Validación cada 10 épocas
        if epoch % 10 == 0 or epoch == 1:
            train_acc = t_correct / t_total

            if has_val:
                val_acc = _val_accuracy(model, val_samples, device)
                current_acc = val_acc
                metric_label = f"val={val_acc:.1f}%"
            else:
                # Sin validation set: usar captcha accuracy como métrica
                captcha_acc, _, _ = evaluate_captchas(
                    model, device, verbose=False
                )
                current_acc = captcha_acc
                metric_label = f"captcha={captcha_acc:.1f}%"

            if current_acc > best_acc:
                best_acc = current_acc
                torch.save({
                    "epoch": epoch,
                    "arch": arch,
                    "seed": seed,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "train_acc": train_acc,
                    "val_acc": current_acc if has_val else 0.0,
                    "captcha_acc": current_acc if not has_val else 0.0,
                    "phase": 1,
                }, best_path)
                no_improve = 0
            else:
                no_improve += 1

            el = time.time() - start
            lr_val = optimizer.param_groups[0]['lr']
            print(f"  P1 E{epoch:3d} | train={train_acc:.4f} | "
                  f"{metric_label} | best_{best_metric}={best_acc:.1f}% | "
                  f"lr={lr_val:.5f} | {el:.0f}s")

            if no_improve >= patience:
                print(f"  Early stopping (no improve for {patience} epochs)")
                break

    elapsed_p1 = time.time() - start
    print(f"\n  === PHASE 1 DONE: {elapsed_p1:.0f}s, Best val={best_val_acc:.1f}% ===")

    # ══════════════════════════════════════════════════════════
    # PHASE 2: Fine-tune with augmentation
    # ══════════════════════════════════════════════════════════
    if augment_intensity > 0 and aug_mult > 1 and epochs_p2 > 0:
        print(f"\n  === PHASE 2: Augmented (intensity={augment_intensity}, "
              f"mult={aug_mult}) ===")

        # Recargar datos con augmentación
        train_aug, _ = load_splits(
            val_ratio=val_ratio, augment_intensity=augment_intensity,
            aug_mult=aug_mult, raw_dir=raw_dir,
        )

        # Combinar train original + augmented
        # (los datos augmentados ya incluyen los originales + copias augmentadas)
        combined = train_aug
        print(f"  Combined train: {len(combined)} samples")

        aug_loader = make_balanced_loader(combined, batch_size=64, shuffle=True)

        # Lower LR for fine-tuning
        optimizer = optim.AdamW(model.parameters(), lr=lr * 0.2, weight_decay=1e-5)
        scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.5)

        no_improve = 0

        for epoch in range(1, epochs_p2 + 1):
            model.train()
            t_loss, t_correct, t_total = 0.0, 0, 0

            for inputs, targets in aug_loader:
                inputs, targets = inputs.to(device), targets.to(device)
                optimizer.zero_grad()
                outputs = model(inputs)
                loss = criterion(outputs, targets)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
                optimizer.step()

                t_loss += loss.item() * inputs.size(0)
                _, preds = outputs.max(1)
                t_total += targets.size(0)
                t_correct += preds.eq(targets).sum().item()

            scheduler.step()

            if epoch % 10 == 0 or epoch == 1:
                train_acc = t_correct / t_total

                if has_val:
                    current_acc = _val_accuracy(model, val_samples, device)
                    metric_label = f"val={current_acc:.1f}%"
                else:
                    current_acc, _, _ = evaluate_captchas(
                        model, device, verbose=False
                    )
                    metric_label = f"captcha={current_acc:.1f}%"

                if current_acc > best_acc:
                    best_acc = current_acc
                    torch.save({
                        "epoch": epoch + epochs_p1,
                        "arch": arch,
                        "seed": seed,
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "train_acc": train_acc,
                        "val_acc": current_acc if has_val else 0.0,
                        "captcha_acc": current_acc if not has_val else 0.0,
                        "phase": 2,
                    }, best_path)
                    no_improve = 0
                else:
                    no_improve += 1

                el = time.time() - start
                print(f"  P2 E{epoch:3d} | train={train_acc:.4f} | "
                      f"{metric_label} | best_{best_metric}={best_acc:.1f}% | "
                      f"{el:.0f}s")

                if no_improve >= patience // 2:
                    print(f"  Early stopping (no improve)")
                    break

    # ══════════════════════════════════════════════════════════
    # Final evaluation
    # ══════════════════════════════════════════════════════════
    elapsed = time.time() - start

    # Recargar best checkpoint
    checkpoint = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    print(f"\n  === FINAL EVAL ===")
    print(f"  Best checkpoint: epoch={checkpoint['epoch']}, "
          f"val_acc={checkpoint['val_acc']:.1f}%")

    captcha_acc, char_acc, errors = evaluate_captchas(
        model, device, verbose=True, raw_dir=raw_dir
    )

    print(f"\n  === SUMMARY ===")
    print(f"  Arch: {arch} | Seed: {seed}")
    print(f"  Captcha acc: {captcha_acc:.1f}%")
    print(f"  Char acc: {char_acc:.1f}%")
    print(f"  Best val: {best_val_acc:.1f}%")
    print(f"  Total time: {elapsed:.0f}s")
    print(f"  Saved: {best_path}")

    return captcha_acc, model


def _val_accuracy(model, val_samples, device):
    """Char-level validation accuracy."""
    if not val_samples:
        return 0.0
    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        for norm, label in val_samples:
            t = torch.from_numpy(norm).float().unsqueeze(0).unsqueeze(0).to(device)
            o = model(t)
            _, p = o.max(1)
            if p.item() == label:
                correct += 1
            total += 1
    return correct / total * 100


# ═══════════════════════════════════════════════════════════════════════════
# Ensemble training
# ═══════════════════════════════════════════════════════════════════════════

def train_ensemble(arch: str, n_models: int = 3, seeds: list = None,
                   **kwargs):
    """
    Entrena N modelos con diferentes seeds para ensemble.

    Args:
        arch: arquitectura
        n_models: cantidad de modelos
        seeds: lista de seeds (si None, usa [42, 123, 456, ...])
        **kwargs: pasado a train_single()
    """
    if seeds is None:
        seeds = [42, 123, 456, 789, 1111][:n_models]

    print(f"\n{'='*60}")
    print(f"  ENSEMBLE TRAINING: {n_models} × {arch}")
    print(f"  Seeds: {seeds}")
    print(f"{'='*60}")

    models = []
    accs = []

    for i, seed in enumerate(seeds):
        print(f"\n─── Model {i+1}/{n_models} (seed={seed}) ───")
        acc, model = train_single(arch, seed=seed, **kwargs)
        models.append(model)
        accs.append(acc)

    print(f"\n{'='*60}")
    print(f"  ENSEMBLE RESULTS:")
    for i, (seed, acc) in enumerate(zip(seeds, accs)):
        print(f"    Model {i+1} (seed={seed}): {acc:.1f}%")
    mean_acc = sum(accs) / len(accs)
    print(f"    Mean: {mean_acc:.1f}%")
    print(f"  (Ensemble voting accuracy evaluated separately)")
    print(f"{'='*60}")

    return models


# ═══════════════════════════════════════════════════════════════════════════
# Evaluate ensemble
# ═══════════════════════════════════════════════════════════════════════════

@torch.no_grad()
def evaluate_ensemble(model_paths, device=None, verbose=True):
    """
    Evalúa un ensemble de modelos guardados.

    Args:
        model_paths: lista de paths a checkpoints
        device: torch device
    """
    if device is None:
        device = torch.device("cpu")

    print(f"\n  === EVALUATING ENSEMBLE ({len(model_paths)} models) ===")

    # Cargar modelos
    models = []
    for path in model_paths:
        cp = torch.load(path, map_location=device, weights_only=False)
        arch = cp.get("arch", "attention")
        seed = cp.get("seed", "?")
        model = create_model(arch, num_classes=N_CLASSES).to(device)
        model.load_state_dict(cp["model_state_dict"])
        model.eval()
        models.append(model)
        print(f"  Loaded {path.name} (arch={arch}, seed={seed})")

    # Evaluar
    files = sorted([f for f in os.listdir(SAMPLES_DIR)
                    if f.endswith(('.jpg', '.PNG', '.png', '.jpeg'))])
    correct, total = 0, 0
    errors = []

    for fname in files:
        stem = Path(fname).stem
        expected = stem.split('_')[0]
        if len(expected) != 7:
            continue
        if not all(c in CHAR_TO_IDX for c in expected):
            continue

        img = cv2.imread(str(SAMPLES_DIR / fname))
        if img is None:
            continue
        chars = segment_captcha(img)
        if len(chars) != 7:
            continue

        # Ensemble prediction
        predicted = ""
        for ci in chars:
            norm = normalize_char(ci)
            t = torch.from_numpy(norm).float().unsqueeze(0).unsqueeze(0).to(device)

            # Sum probabilities across models
            sum_probs = None
            for model in models:
                o = model(t)
                probs = F.softmax(o, dim=1)
                sum_probs = probs if sum_probs is None else sum_probs + probs

            _, pred = sum_probs.max(1)
            predicted += IDX_TO_CHAR[pred.item()]

        if predicted == expected:
            correct += 1
        else:
            errors.append((fname, expected, predicted))
        total += 1

    acc = correct / total * 100 if total else 0
    if verbose:
        print(f"  Ensemble: {correct}/{total} = {acc:.1f}%")
        if errors:
            print(f"  Errors ({len(errors)}):")
            for f, e, p in errors[:10]:
                diffs = ''.join('^' if a != b else ' ' for a, b in zip(e, p))
                print(f"    {f}: exp={e} got={p}")
                print(f"           {diffs}")

    return acc, errors


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Train v3 — improved CNN for IMSS captchas")
    parser.add_argument("--arch", default="attention",
                        choices=["original", "wide", "residual", "attention"],
                        help="Arquitectura (default: attention)")
    parser.add_argument("--ensemble", type=int, default=0,
                        help="Entrenar N modelos para ensemble (default: 0 = single)")
    parser.add_argument("--epochs-p1", type=int, default=200,
                        help="Épocas fase 1 clean (default: 200)")
    parser.add_argument("--epochs-p2", type=int, default=100,
                        help="Épocas fase 2 augmented (default: 100)")
    parser.add_argument("--aug-intensity", type=float, default=0.6,
                        help="Intensidad augmentación 0-1 (default: 0.6)")
    parser.add_argument("--aug-mult", type=int, default=3,
                        help="Multiplicador augmentación (default: 3)")
    parser.add_argument("--lr", type=float, default=0.003,
                        help="Learning rate (default: 0.003)")
    parser.add_argument("--label-smoothing", type=float, default=0.0,
                        help="Label smoothing (default: 0.0)")
    parser.add_argument("--val-ratio", type=float, default=0.15,
                        help="Fracción para validación (default: 0.15)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--seeds", type=int, nargs="*",
                        help="Seeds para ensemble (default: 42 123 456)")
    parser.add_argument("--raw-dir", type=str, default=None,
                        help="Directorio con imágenes crudas (default: raw_captchas/)")
    parser.add_argument("--eval-ensemble", type=str, nargs="*",
                        help="Evaluar ensemble desde paths de checkpoints")
    parser.add_argument("--suffix", type=str, default="",
                        help="Sufijo para nombre del checkpoint")

    args = parser.parse_args()

    # Raw dir
    raw_dir = None
    if args.raw_dir:
        raw_dir = Path(args.raw_dir)
    else:
        default_raw = Path(__file__).resolve().parent.parent / "raw_captchas"
        if default_raw.exists():
            raw_dir = default_raw

    # Evaluar ensemble existente
    if args.eval_ensemble:
        paths = [Path(p) for p in args.eval_ensemble]
        evaluate_ensemble(paths)
        return

    # Entrenar
    if args.ensemble > 1:
        seeds = args.seeds or [42 + i * 81 for i in range(args.ensemble)]
        train_ensemble(
            args.arch, n_models=args.ensemble, seeds=seeds[:args.ensemble],
            epochs_p1=args.epochs_p1, epochs_p2=args.epochs_p2,
            val_ratio=args.val_ratio, augment_intensity=args.aug_intensity,
            aug_mult=args.aug_mult, label_smoothing=args.label_smoothing,
            lr=args.lr, raw_dir=raw_dir, suffix=args.suffix,
        )
    else:
        train_single(
            args.arch, seed=args.seed,
            epochs_p1=args.epochs_p1, epochs_p2=args.epochs_p2,
            val_ratio=args.val_ratio, augment_intensity=args.aug_intensity,
            aug_mult=args.aug_mult, label_smoothing=args.label_smoothing,
            lr=args.lr, raw_dir=raw_dir, suffix=args.suffix,
        )


if __name__ == "__main__":
    main()
