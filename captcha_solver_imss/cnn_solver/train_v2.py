"""
train_v2.py
CNN with 62 classes (A-Z + a-z + 0-9) — preserves original case.
Phase 1: train on clean data
Phase 2: fine-tune with light augmentation
"""
import os
import random
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from .model import CaptchaCNN, count_params

# 62 classes: A-Z (0-25), a-z (26-51), 0-9 (52-61)
CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
CHAR_TO_IDX = {c: i for i, c in enumerate(CHARS)}
IDX_TO_CHAR = {i: c for i, c in enumerate(CHARS)}
N_CLASSES = 62

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "test_samples"
MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def segment_captcha(img, expected_len=7):
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    h, w = gray.shape
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    v_proj = np.sum(binary, axis=0) / 255.0
    m = np.max(v_proj) if np.max(v_proj) > 0 else 1.0
    v_proj_norm = v_proj / m
    in_gap = False
    segments, prev_end = [], 0
    for col in range(w):
        active = v_proj_norm[col] >= 0.1
        if active and in_gap:
            if col - gap_start >= 2 and gap_start - prev_end >= 3:
                segments.append((prev_end, gap_start))
                prev_end = col
            in_gap = False
        elif not active and not in_gap:
            gap_start = col
            in_gap = True
    if w - prev_end >= 3:
        segments.append((prev_end, w))
    if len(segments) != expected_len:
        sw = w // expected_len
        segments = [(i*sw, (i+1)*sw) for i in range(expected_len)]
    chars = []
    for s, e in segments:
        roi = binary[:, s:e]
        cols = np.any(roi, axis=0)
        rows = np.any(roi, axis=1)
        if not np.any(cols) or not np.any(rows):
            chars.append(np.zeros((h, 1), dtype=np.uint8)); continue
        x1, x2 = np.where(cols)[0][[0,-1]]
        y1, y2 = np.where(rows)[0][[0,-1]]
        y1, y2 = max(0,y1-1), min(h,y2+2)
        x1, x2 = max(0,x1-1), min(roi.shape[1],x2+2)
        chars.append(roi[y1:y2, x1:x2])
    return chars


def normalize_char(char_img, target_size=32):
    h, w = char_img.shape
    s = min(target_size/max(h,1), target_size/max(w,1))
    nh, nw = max(1,int(h*s)), max(1,int(w*s))
    r = cv2.resize(char_img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    c = np.zeros((target_size, target_size), dtype=np.float32)
    yo, xo = (target_size-nh)//2, (target_size-nw)//2
    c[yo:yo+nh, xo:xo+nw] = r / 255.0
    return c


def _rotate(img, angle):
    M = cv2.getRotationMatrix2D((16,16), angle, 1.0)
    return cv2.warpAffine(img, M, (32,32), borderValue=0.0)


def _shift(img, dx, dy):
    M = np.float32([[1,0,dx],[0,1,dy]])
    return cv2.warpAffine(img, M, (32,32), borderValue=0.0)


def augment_light(img):
    """Light augmentation for fine-tuning."""
    if random.random() < 0.5:
        img = _rotate(img, random.uniform(-5, 5))
    if random.random() < 0.5:
        img = _shift(img, random.uniform(-1, 1), random.uniform(-1, 1))
    return img


def load_all_chars(use_augmentation=False):
    """Load characters preserving ORIGINAL case."""
    samples = []
    class_counts = {i:0 for i in range(N_CLASSES)}
    files = sorted([f for f in os.listdir(SAMPLES_DIR) if f.endswith(('.jpg','.PNG'))])
    
    for fname in files:
        stem = Path(fname).stem
        label = stem.split('_')[0]  # Keep original case!
        if len(label) != 7:
            continue
        if not all(c in CHAR_TO_IDX for c in label):
            continue
        
        img = cv2.imread(str(SAMPLES_DIR / fname))
        if img is None: continue
        chars = segment_captcha(img)
        if len(chars) != 7: continue
        
        for ci, exp_c in zip(chars, label):
            norm = normalize_char(ci)
            samples.append((norm, CHAR_TO_IDX[exp_c]))
            class_counts[CHAR_TO_IDX[exp_c]] += 1
    
    # Add synthetic for classes with < 3 samples
    for cls_idx, cnt in class_counts.items():
        if cnt >= 3: continue
        ch = IDX_TO_CHAR[cls_idx]
        # Find a visually similar class with data
        for src_idx, src_cnt in sorted(class_counts.items(), key=lambda x: -x[1]):
            if src_cnt < 3: continue
            src_ch = IDX_TO_CHAR[src_idx]
            # Only mix same letter different case, or same visual
            if ch.upper() == src_ch.upper() or ch.lower() == src_ch.lower():
                # Clone src images with label changed
                count_added = 0
                for norm, _ in random.sample([s for s in samples if s[1]==src_idx],
                                              min(5, len([s for s in samples if s[1]==src_idx]))):
                    # Add slight noise
                    noisy = norm + np.random.randn(32,32).astype(np.float32)*0.02
                    samples.append((np.clip(noisy,0,1), cls_idx))
                    count_added += 1
                break
    
    # Print distribution
    existing = {i for _, i in samples}
    missing = [c for c in CHARS if CHAR_TO_IDX[c] not in existing]
    
    if use_augmentation:
        # Augmented version: add rotated/shifted copies for underrepresented classes
        augmented = []
        for norm, label in samples:
            augmented.append((norm, label))
        # Add light augments for classes with < 10 samples
        counts = {i:0 for i in range(N_CLASSES)}
        for _, l in samples: counts[l] = counts.get(l,0)+1
        for norm, label in samples:
            if counts.get(label,0) < 10:
                for _ in range(2):
                    aug = augment_light(norm.copy())
                    augmented.append((aug, label))
        samples = augmented
    
    print(f"  [CNN] Total: {len(samples)} samples, {len(existing)}/{N_CLASSES} classes")
    if missing:
        print(f"  [CNN] No-data classes: {missing}")
    
    return samples


@torch.no_grad()
def evaluate_captchas(model, device, verbose=True):
    model.eval()
    files = sorted([f for f in os.listdir(SAMPLES_DIR) if f.endswith(('.jpg','.PNG'))])
    correct, total = 0, 0
    errors = []
    
    for fname in files:
        stem = Path(fname).stem
        expected = stem.split('_')[0]
        if len(expected) != 7: continue
        if not all(c in CHAR_TO_IDX for c in expected): continue
        
        img = cv2.imread(str(SAMPLES_DIR / fname))
        if img is None: continue
        chars = segment_captcha(img)
        if len(chars) != 7: continue
        
        predicted = ""
        for ci in chars:
            norm = normalize_char(ci)
            t = torch.from_numpy(norm).float().unsqueeze(0).unsqueeze(0).to(device)
            o = model(t)
            _, p = o.max(1)
            predicted += IDX_TO_CHAR[p.item()]
        
        if predicted == expected:
            correct += 1
        else:
            errors.append((fname, expected, predicted))
        total += 1
    
    acc = correct/total*100 if total else 0
    if verbose:
        print(f"  [CNN] Captcha: {correct}/{total} = {acc:.1f}%")
        if errors:
            print(f"  [CNN] Errors ({len(errors)}):")
            for f, e, p in errors[:8]:
                diffs = ''.join('^' if a!=b else ' ' for a,b in zip(e,p))
                print(f"    {f}: exp={e} got={p}")
                print(f"           {diffs}")
    return acc, errors


def train():
    device = torch.device("cpu")
    print(f"  [CNN] Device: {device}")
    print(f"  [CNN] Classes: {N_CLASSES} (A-Z a-z 0-9)")
    
    # Phase 1: clean data
    samples = load_all_chars(use_augmentation=False)
    imgs = np.array([s[0] for s in samples], dtype=np.float32)
    labels = np.array([s[1] for s in samples], dtype=np.int64)
    
    # Convert to tensor efficiently
    imgs_t = torch.FloatTensor(np.expand_dims(imgs, 1))  # (N,1,32,32)
    lbls_t = torch.LongTensor(labels)
    
    dataset = torch.utils.data.TensorDataset(imgs_t, lbls_t)
    loader = torch.utils.data.DataLoader(dataset, batch_size=64, shuffle=True)
    
    model = CaptchaCNN(num_classes=N_CLASSES).to(device)
    print(f"  [CNN] Params: {count_params(model):,}")
    
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=0.003, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=60, gamma=0.5)
    
    best_path = MODEL_DIR / "best_v2.pt"
    best_acc = 0.0
    start = time.time()
    
    print(f"\n  === PHASE 1: Clean data ({len(samples)} samples) ===")
    for epoch in range(1, 301):
        model.train()
        t_loss, t_correct, t_total = 0.0, 0, 0
        for inputs, targets in loader:
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            t_loss += loss.item() * inputs.size(0)
            _, preds = outputs.max(1)
            t_total += targets.size(0)
            t_correct += preds.eq(targets).sum().item()
        scheduler.step()
        
        if epoch % 10 == 0 or epoch == 1:
            train_acc = t_correct / t_total
            captcha_acc, _ = evaluate_captchas(model, device, verbose=False)
            el = time.time()-start
            lr = optimizer.param_groups[0]['lr']
            print(f"  [CNN] E{epoch:3d} | train={train_acc:.4f} | captcha={captcha_acc:.1f}% | lr={lr:.5f} | {el:.0f}s")
            if captcha_acc > best_acc:
                best_acc = captcha_acc
                torch.save({"epoch":epoch, "model_state_dict":model.state_dict(),
                            "train_acc":train_acc, "captcha_acc":captcha_acc}, best_path)
                print(f"  [CNN] -> BEST {captcha_acc:.1f}% saved")
    
    total = time.time()-start
    print(f"\n  === PHASE 1 DONE: {total:.0f}s, Best={best_acc:.1f}% ===")
    
    # Phase 2: fine-tune with light augmentation
    print("\n  === PHASE 2: Fine-tune with light augmentation ===")
    aug_samples = load_all_chars(use_augmentation=True)
    aug_imgs = np.array([s[0] for s in aug_samples], dtype=np.float32)
    aug_labels = np.array([s[1] for s in aug_samples], dtype=np.int64)
    aug_imgs_t = torch.FloatTensor(np.expand_dims(aug_imgs, 1))
    aug_lbls_t = torch.LongTensor(aug_labels)
    
    aug_dataset = torch.utils.data.TensorDataset(aug_imgs_t, aug_lbls_t)
    aug_loader = torch.utils.data.DataLoader(aug_dataset, batch_size=64, shuffle=True)
    
    # Lower LR for fine-tuning
    optimizer = optim.AdamW(model.parameters(), lr=0.0005, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.5)
    
    for epoch in range(1, 151):
        model.train()
        t_loss, t_correct, t_total = 0.0, 0, 0
        for inputs, targets in aug_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            t_loss += loss.item() * inputs.size(0)
            _, preds = outputs.max(1)
            t_total += targets.size(0)
            t_correct += preds.eq(targets).sum().item()
        scheduler.step()
        
        if epoch % 10 == 0 or epoch == 1:
            train_acc = t_correct / t_total
            captcha_acc, _ = evaluate_captchas(model, device, verbose=False)
            el = time.time()-total
            print(f"  [CNN] FT E{epoch:3d} | train={train_acc:.4f} | captcha={captcha_acc:.1f}% | {el:.0f}s")
            if captcha_acc > best_acc:
                best_acc = captcha_acc
                torch.save({"epoch":epoch+300, "model_state_dict":model.state_dict(),
                            "train_acc":train_acc, "captcha_acc":captcha_acc}, best_path)
                print(f"  [CNN] -> BEST {captcha_acc:.1f}% saved (v2)")
    
    total2 = time.time()-start
    print(f"\n  === TRAINING COMPLETE: {total2:.0f}s ===")
    
    # Final eval
    checkpoint = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    final_acc, errors = evaluate_captchas(model, device, verbose=True)
    return final_acc


if __name__ == "__main__":
    train()
