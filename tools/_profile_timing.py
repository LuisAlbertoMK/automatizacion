"""
Profile captcha solver timing in detail.
"""
import time
from pathlib import Path

import cv2
import numpy as np

samples_dir = Path(__file__).resolve().parent / "captcha_solver_imss" / "test_samples"
files = sorted(list(samples_dir.glob("*.jpg")) + list(samples_dir.glob("*.PNG")))

print(f"Total labeled captchas: {len(files)}")
print()

# ── 1. OpenCV read time ──
print("=== 1. OpenCV read ===")
img_cache = {}
start = time.time()
for f in files:
    img = cv2.imread(str(f))
    img_cache[f.name] = img
elapsed = (time.time() - start) / len(files) * 1000
print(f"  {elapsed:.1f}ms avg ({len(files)} files)")

# ── 2. Segmentation time ──
print()
print("=== 2. Segmentation + normalize ===")
from captcha_solver_imss.cnn_solver.train_v2 import normalize_char, segment_captcha

start = time.time()
chars_data = {}
for f in files:
    img = img_cache[f.name]
    chars = segment_captcha(img)
    norms = [normalize_char(c) for c in chars]
    chars_data[f.name] = (chars, norms)
elapsed = (time.time() - start) / len(files) * 1000
print(f"  {elapsed:.1f}ms avg")

# ── 3. CNN inference (single vs batch) ──
print()
print("=== 3. CNN inference ===")
import torch

device = torch.device("cpu")
from captcha_solver_imss.cnn_solver.model_v2 import create_model

model_path = Path(__file__).resolve().parent / "captcha_solver_imss" / "cnn_solver" / "models" / "original_s42_v3_full.pt"
checkpoint = torch.load(model_path, map_location=device, weights_only=False)
model = create_model("original", num_classes=62).to(device)
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()

# Single char inference
start = time.time()
n_chars = 0
for fname, (chars, norms) in list(chars_data.items())[:20]:  # First 20 captchas
    for norm in norms:
        t = torch.from_numpy(norm).float().unsqueeze(0).unsqueeze(0).to(device)
        with torch.no_grad():
            o = model(t)
            _, p = o.max(1)
        n_chars += 1
elapsed_ms = (time.time() - start) / n_chars * 1000
print(f"  Single char: {elapsed_ms:.2f}ms/char = {elapsed_ms*7:.1f}ms/captcha")

# Batch inference (7 chars as batch)
start = time.time()
n_captchas = 0
for fname, (chars, norms) in list(chars_data.items())[:20]:
    batch = np.array(norms)
    batch_t = torch.FloatTensor(np.expand_dims(batch, 1)).to(device)
    with torch.no_grad():
        o = model(batch_t)
        _, preds = o.max(1)
    n_captchas += 1
elapsed_ms = (time.time() - start) / n_captchas * 1000
print(f"  Batch 7:     {elapsed_ms:.1f}ms/captcha")

# ── 4. Full solver_v2 timing ──
print()
print("=== 4. Full solver_v2 solve ===")
from captcha_solver_imss.solver import IMSCaptchaSolver

s = IMSCaptchaSolver(use_easyocr=False, use_tesseract=False, verbose=False)

start = time.time()
correct = 0
n_test = min(50, len(files))
times = []
for f in files[:n_test]:
    expected = f.stem.split("_")[0]
    img = cv2.imread(str(f))
    t0 = time.time()
    result = s.solve(img)
    t = (time.time() - t0) * 1000
    times.append(t)
    if result["value"] == expected:
        correct += 1

avg_t = sum(times) / len(times)
min_t = min(times)
max_t = max(times)
elapsed = time.time() - start
print(f"  {correct}/{n_test} = {correct/n_test*100:.1f}%")
print(f"  Avg: {avg_t:.0f}ms, Min: {min_t:.0f}ms, Max: {max_t:.0f}ms")
print(f"  Total: {elapsed:.1f}s for {n_test} captchas")

# ── 5. Optimized: pre-alloc + batch inference ──
print()
print("=== 5. Optimized path (batch + skip solver overhead) ===")
# Direct CNN solve
from captcha_solver_imss.cnn_solver.solver_v2 import CNNSolverV2

s2 = CNNSolverV2(verbose=False)

start = time.time()
correct = 0
for f in files[:n_test]:
    expected = f.stem.split("_")[0]
    img = cv2.imread(str(f))
    t0 = time.time()
    result = s2.solve(img)
    t = (time.time() - t0) * 1000
    if result["value"] == expected:
        correct += 1

avg_t = sum(times) / len(times)
elapsed = time.time() - start
print(f"  {correct}/{n_test} = {correct/n_test*100:.1f}%")
print(f"  Avg: {avg_t:.0f}ms, Total: {elapsed:.1f}s")
