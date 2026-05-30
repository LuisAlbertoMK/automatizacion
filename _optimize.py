"""
Optimize CNN model: ONNX export + INT8 quantization + benchmark.
"""
import sys, time, os
sys.path.insert(0, 'captcha_solver_imss')
from pathlib import Path
from cnn_solver.train_v2 import segment_captcha, normalize_char, CHAR_TO_IDX, IDX_TO_CHAR, N_CLASSES
from cnn_solver.model_v2 import create_model
import torch
import torch.nn.functional as F
import numpy as np
import cv2

MODEL_DIR = Path('captcha_solver_imss/cnn_solver/models')
MODEL_PATH = MODEL_DIR / 'attention_s42_409_v4.pt'

# ── 1. Load PyTorch model ──
print("=== 1. Loading PyTorch model ===")
device = torch.device('cpu')
cp = torch.load(MODEL_PATH, map_location=device, weights_only=False)
model = create_model(cp['arch'], num_classes=N_CLASSES).to(device)
model.load_state_dict(cp['model_state_dict'])
model.eval()
print(f"  Arquitectura: {cp['arch']}")
print(f"  Seed: {cp['seed']}")
print(f"  Val acc: {cp.get('val_acc', 0):.1f}%")

# ── 2. ONNX export ──
print("\n=== 2. Exporting to ONNX ===")
onnx_path = MODEL_DIR / 'attention_s42_409_v4.onnx'
dummy_input = torch.randn(7, 1, 32, 32)  # batch of 7 chars

torch.onnx.export(
    model,
    dummy_input,
    onnx_path,
    input_names=['input'],
    output_names=['output'],
    dynamic_axes={
        'input': {0: 'batch_size'},
        'output': {0: 'batch_size'},
    },
    opset_version=17,
)
print(f"  ONNX saved: {onnx_path}")
print(f"  Size: {onnx_path.stat().st_size / 1024:.0f} KB")

# ── 3. ONNX Runtime session ──
print("\n=== 3. ONNX Runtime ===")
import onnxruntime as ort

# Config: use all CPU providers
available = ort.get_available_providers()
print(f"  Available providers: {available}")

# Try INT8 quantization first
print("\n=== 4. INT8 Quantization ===")
from onnxruntime.quantization import quantize_dynamic, QuantType, quantize_static

q8_path = MODEL_DIR / 'attention_s42_409_v4_q8.onnx'

# Dynamic quantization (simpler, works on CPU)
quantize_dynamic(
    str(onnx_path),
    str(q8_path),
    weight_type=QuantType.QInt8,
)
q8_size = q8_path.stat().st_size / 1024
print(f"  INT8 quantized: {q8_path}")
print(f"  Size: {q8_size:.0f} KB")

# ── 5. Benchmark ──
print("\n=== 5. Benchmark ===")
samples_dir = Path('captcha_solver_imss/test_samples')

# Load test images (first 100)
test_imgs = []
test_labels = []
for f in sorted(samples_dir.iterdir())[:100]:
    if f.suffix not in ('.jpg', '.PNG'):
        continue
    label = f.stem.split('_')[0]
    if len(label) == 7 and all(c in CHAR_TO_IDX for c in label):
        test_imgs.append(str(f))
        test_labels.append(label)

print(f"  Test images: {len(test_imgs)}")

def benchmark(engine_name, solve_fn, n_warmup=5):
    """Benchmark a solver function."""
    # Warmup
    for f in test_imgs[:n_warmup]:
        solve_fn(f)
    
    # Measure
    times = []
    correct_chars = 0
    total_chars = 0
    correct_captchas = 0
    
    for img_path, expected in zip(test_imgs, test_labels):
        img = cv2.imread(img_path)
        if img is None:
            continue
        start = time.time()
        predicted = solve_fn(img)
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)
        
        if predicted and len(predicted) == 7:
            for a, b in zip(predicted, expected):
                if a == b:
                    correct_chars += 1
                total_chars += 1
            if predicted == expected:
                correct_captchas += 1
    
    avg = sum(times) / len(times)
    char_acc = correct_chars / total_chars * 100 if total_chars else 0
    captcha_acc = correct_captchas / len(test_labels) * 100
    print(f"  {engine_name}:")
    print(f"    Avg: {avg:.1f}ms")
    print(f"    Char acc: {char_acc:.1f}%")
    print(f"    Captcha acc: {captcha_acc:.1f}%")
    print(f"    Min: {min(times):.1f}ms  Max: {max(times):.1f}ms")
    return avg

# PyTorch baseline
def pytorch_solve(img):
    chars = segment_captcha(img)
    if len(chars) != 7:
        return ""
    pred = ""
    for ci in chars:
        norm = normalize_char(ci)
        t = torch.from_numpy(norm).float().unsqueeze(0).unsqueeze(0).to(device)
        o = model(t)
        _, p = o.max(1)
        pred += IDX_TO_CHAR[p.item()]
    return pred

print("\n  --- PyTorch CPU ---")
pt_time = benchmark("PyTorch", pytorch_solve)

# ONNX session (FP32)
ort_session_fp32 = ort.InferenceSession(str(onnx_path), providers=['CPUExecutionProvider'])

def onnx_fp32_solve(img):
    chars = segment_captcha(img)
    if len(chars) != 7:
        return ""
    batch = np.array([normalize_char(c) for c in chars], dtype=np.float32)
    batch = np.expand_dims(batch, 1)  # (7, 1, 32, 32)
    outputs = ort_session_fp32.run(['output'], {'input': batch})
    probs = torch.from_numpy(outputs[0]).softmax(dim=1)
    _, preds = probs.max(1)
    return ''.join(IDX_TO_CHAR[p.item()] for p in preds)

print("\n  --- ONNX FP32 ---")
onnx_fp32_time = benchmark("ONNX FP32", onnx_fp32_solve)

# ONNX session (INT8)
ort_session_q8 = ort.InferenceSession(str(q8_path), providers=['CPUExecutionProvider'])

def onnx_q8_solve(img):
    chars = segment_captcha(img)
    if len(chars) != 7:
        return ""
    batch = np.array([normalize_char(c) for c in chars], dtype=np.float32)
    batch = np.expand_dims(batch, 1)
    outputs = ort_session_q8.run(['output'], {'input': batch})
    probs = torch.from_numpy(outputs[0]).softmax(dim=1)
    _, preds = probs.max(1)
    return ''.join(IDX_TO_CHAR[p.item()] for p in preds)

print("\n  --- ONNX INT8 ---")
onnx_q8_time = benchmark("ONNX INT8", onnx_q8_solve)

print("\n" + "=" * 50)
print("SUMMARY")
print("=" * 50)
print(f"  PyTorch CPU:  {pt_time:.1f}ms")
print(f"  ONNX FP32:    {onnx_fp32_time:.1f}ms  ({pt_time/onnx_fp32_time:.1f}x)")
print(f"  ONNX INT8:    {onnx_q8_time:.1f}ms  ({pt_time/onnx_q8_time:.1f}x)")
