"""
train.py
Train CNN on segmented captcha characters.

Strategy:
  - Train WITHOUT augmentation first (model needs to see clean data)
  - ALL data for training (no val split — evaluate on captcha level)
  - Fixed LR with steps, NO label smoothing
  - Only 31 real classes (skip 5 missing: I,O,Z,0,1)
"""
import time
import random
import numpy as np
import os
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
import cv2

from .model import CaptchaCNN, count_params

N_CLASSES = 36
CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
CHAR_TO_IDX = {c: i for i, c in enumerate(CHARS)}
IDX_TO_CHAR = {i: c for i, c in enumerate(CHARS)}

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "test_samples"
MODEL_DIR = Path(__file__).resolve().parent / "models"


def segment_captcha(img, expected_len=7):
    """Segment captcha into 7 char images (inverted binary)."""
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    h, w = gray.shape
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    v_proj = np.sum(binary, axis=0) / 255.0
    max_proj = np.max(v_proj) if np.max(v_proj) > 0 else 1.0
    v_proj_norm = v_proj / max_proj

    in_gap = False
    segments = []
    prev_end = 0
    for col in range(w):
        is_active = v_proj_norm[col] >= 0.1
        if is_active and in_gap:
            gap_end = col
            if gap_end - gap_start >= 2 and gap_start - prev_end >= 3:
                segments.append((prev_end, gap_start))
                prev_end = gap_end
            in_gap = False
        elif not is_active and not in_gap:
            gap_start = col
            in_gap = True
    if w - prev_end >= 3:
        segments.append((prev_end, w))

    if len(segments) != expected_len:
        seg_w = w // expected_len
        segments = [(i * seg_w, (i + 1) * seg_w) for i in range(expected_len)]

    chars = []
    for start, end in segments:
        char_roi = binary[:, start:end]
        cols = np.any(char_roi, axis=0)
        rows = np.any(char_roi, axis=1)
        if not np.any(cols) or not np.any(rows):
            chars.append(np.zeros((h, 1), dtype=np.uint8))
            continue
        x1, x2 = np.where(cols)[0][[0, -1]]
        y1, y2 = np.where(rows)[0][[0, -1]]
        y1, y2 = max(0, y1 - 1), min(h, y2 + 2)
        x1, x2 = max(0, x1 - 1), min(char_roi.shape[1], x2 + 2)
        chars.append(char_roi[y1:y2, x1:x2])
    return chars


def normalize_char(char_img, target_size=32):
    """Pad + resize char to target_size², preserving aspect ratio."""
    h, w = char_img.shape
    scale = min(target_size / max(h, 1), target_size / max(w, 1))
    new_h, new_w = max(1, int(h * scale)), max(1, int(w * scale))
    resized = cv2.resize(char_img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    canvas = np.zeros((target_size, target_size), dtype=np.float32)
    y_off = (target_size - new_h) // 2
    x_off = (target_size - new_w) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized / 255.0
    return canvas


def load_all_chars():
    """Extract all (char_image, label) pairs from labeled captchas."""
    samples = []
    files = sorted([f for f in os.listdir(SAMPLES_DIR)
                    if f.endswith(('.jpg', '.PNG'))])

    for fname in files:
        stem = Path(fname).stem
        label = stem.split('_')[0].upper()
        if len(label) != 7:
            continue
        if not all(c in CHAR_TO_IDX for c in label):
            continue

        img = cv2.imread(str(SAMPLES_DIR / fname))
        if img is None:
            continue
        chars = segment_captcha(img, expected_len=7)
        if len(chars) != 7:
            continue
        for char_img, expected_char in zip(chars, label):
            norm = normalize_char(char_img)
            samples.append((norm, CHAR_TO_IDX[expected_char]))

    print(f"  [CNN] Total char samples: {len(samples)}")
    classes = set(l for _, l in samples)
    print(f"  [CNN] Classes covered: {len(classes)}/36")
    missing = [c for c in CHARS if CHAR_TO_IDX[c] not in classes]
    print(f"  [CNN] Missing classes: {missing}")
    return samples


def evaluate_captchas(model, device, verbose=True):
    """Full captcha accuracy on all labeled images."""
    model.eval()
    files = sorted([f for f in os.listdir(SAMPLES_DIR)
                    if f.endswith(('.jpg', '.PNG'))])

    correct = 0
    total = 0
    errors = []

    for fname in files:
        stem = Path(fname).stem
        expected = stem.split('_')[0].upper()
        if len(expected) != 7:
            continue

        img = cv2.imread(str(SAMPLES_DIR / fname))
        if img is None:
            continue

        chars = segment_captcha(img, expected_len=7)
        if len(chars) != 7:
            continue

        predicted = ""
        for char_img in chars:
            norm = normalize_char(char_img)
            tensor = torch.from_numpy(norm).float().unsqueeze(0).unsqueeze(0).to(device)
            with torch.no_grad():
                output = model(tensor)
                _, pred = output.max(1)
            predicted += IDX_TO_CHAR[pred.item()]

        if predicted.upper() == expected.upper():
            correct += 1
        else:
            errors.append((fname, expected, predicted))
        total += 1

    accuracy = correct / total * 100 if total > 0 else 0
    if verbose:
        print(f"  [CNN] Captcha accuracy: {correct}/{total} = {accuracy:.1f}%")
        if errors and verbose:
            print(f"  [CNN] Sample errors:")
            for f, e, p in errors[:5]:
                print(f"    {f}: expected={e} got={p}")
    return accuracy, errors


@torch.no_grad()
def per_char_accuracy(model, samples, device):
    """Compute per-character accuracy."""
    model.eval()
    correct = 0
    total = 0
    class_correct = {}
    class_total = {}

    for img, label in samples:
        tensor = torch.from_numpy(img).float().unsqueeze(0).unsqueeze(0).to(device)
        output = model(tensor)
        _, pred = output.max(1)
        total += 1
        if pred.item() == label:
            correct += 1
            class_correct[label] = class_correct.get(label, 0) + 1
        class_total[label] = class_total.get(label, 0) + 1

    acc = correct / total if total > 0 else 0
    return acc, class_correct, class_total


def train():
    device = torch.device("cpu")  # force CPU
    print(f"  [CNN] Device: {device}")

    # Load ALL data (no augmentation, no split)
    samples = load_all_chars()
    imgs = torch.FloatTensor([s[0] for s in samples]).unsqueeze(1)  # (N, 1, 32, 32)
    labels = torch.LongTensor([s[1] for s in samples])
    print(f"  [CNN] Data tensor: {imgs.shape}")

    # Dataset loader (WITHOUT augmentation — we want the model to learn clean chars first)
    dataset = torch.utils.data.TensorDataset(imgs, labels)
    loader = torch.utils.data.DataLoader(dataset, batch_size=64, shuffle=True)

    # Model
    model = CaptchaCNN(num_classes=N_CLASSES).to(device)
    print(f"  [CNN] Params: {count_params(model):,}")

    criterion = nn.CrossEntropyLoss()  # NO label smoothing
    optimizer = optim.AdamW(model.parameters(), lr=0.003, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=50, gamma=0.5)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    best_path = MODEL_DIR / "best.pt"
    best_captcha_acc = 0.0
    start = time.time()

    for epoch in range(1, 301):
        model.train()
        total_loss = 0.0
        train_correct = 0
        train_total = 0

        for inputs, targets in loader:
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * inputs.size(0)
            _, preds = outputs.max(1)
            train_total += targets.size(0)
            train_correct += preds.eq(targets).sum().item()

        scheduler.step()

        if epoch % 10 == 0 or epoch == 1:
            train_acc = train_correct / train_total

            # Per-char accuracy on clean data
            char_acc, _, _ = per_char_accuracy(model, samples, device)

            # Captcha accuracy
            captcha_acc, _ = evaluate_captchas(model, device, verbose=False)

            elapsed = time.time() - start
            print(f"  [CNN] Epoch {epoch:3d} | "
                  f"Train acc={train_acc:.4f} | "
                  f"Char acc={char_acc:.4f} | "
                  f"Captcha={captcha_acc:.1f}% | "
                  f"LR={optimizer.param_groups[0]['lr']:.5f} | "
                  f"{elapsed:.0f}s")

            # Save if best captcha accuracy
            if captcha_acc > best_captcha_acc:
                best_captcha_acc = captcha_acc
                torch.save({
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "train_acc": train_acc,
                    "char_acc": char_acc,
                    "captcha_acc": captcha_acc,
                }, best_path)
                print(f"  [CNN] -> BEST captcha ({captcha_acc:.1f}%) saved to {best_path}")

            # Early exit if perfect accuracy
            if captcha_acc >= 99.0:
                print(f"  [CNN] Near-perfect captcha accuracy! Stopping.")
                break

    total_time = time.time() - start
    print(f"\n  [CNN] Done! {total_time:.0f}s")
    print(f"  [CNN] Best captcha accuracy: {best_captcha_acc:.1f}%")

    # Load best and final evaluation
    checkpoint = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    final_acc, errors = evaluate_captchas(model, device, verbose=True)

    # Show per-class accuracy
    char_acc, class_correct, class_total = per_char_accuracy(model, samples, device)
    print(f"\n  [CNN] Per-class accuracy:")
    for label in sorted(class_total.keys()):
        c = class_correct.get(label, 0)
        t = class_total[label]
        ch = IDX_TO_CHAR[label]
        bar = "#" * int(c / max(t, 1) * 20)
        print(f"    {ch}: {c}/{t} = {c/max(t,1)*100:.0f}% {bar}")

    return final_acc


if __name__ == "__main__":
    train()
