"""
Benchmark all inference backends: PyTorch, ONNX, TorchScript.
"""
import sys, time, os, gc
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
ONNX_PATH = MODEL_DIR / 'attention_s42_409_v4.onnx'

device = torch.device('cpu')

# ── Load PyTorch model ──
cp = torch.load(MODEL_PATH, map_location=device, weights_only=False)
pt_model = create_model(cp['arch'], num_classes=N_CLASSES).to(device)
pt_model.load_state_dict(cp['model_state_dict'])
pt_model.eval()

# ── TorchScript (script) ──
ts_model = torch.jit.script(pt_model)
ts_model.eval()

# ── TorchScript (trace) ──
dummy = torch.randn(7, 1, 32, 32)
ts_traced = torch.jit.trace(pt_model, dummy)
ts_traced.eval()

# ── ONNX Runtime ──
import onnxruntime as ort
ort_session = ort.InferenceSession(str(ONNX_PATH), providers=['CPUExecutionProvider'])

# ── Load test images ──
samples_dir = Path('captcha_solver_imss/test_samples')
test_data = []
for f in sorted(samples_dir.iterdir()):
    if f.suffix not in ('.jpg', '.PNG'):
        continue
    label = f.stem.split('_')[0]
    if len(label) == 7 and all(c in CHAR_TO_IDX for c in label):
        test_data.append((str(f), label))

print(f"Test images: {len(test_data)}")
print()

def run_benchmark(name, solve_fn, data, warmup=3):
    """Benchmark a solve function. Returns (avg_ms, char_acc, captcha_acc)."""
    # Warmup
    for f, _ in data[:warmup]:
        solve_fn(cv2.imread(f))
    
    gc.collect()
    times = []
    char_correct = 0
    char_total = 0
    captcha_correct = 0
    
    for img_path, expected in data:
        img = cv2.imread(img_path)
        if img is None:
            continue
        start = time.perf_counter()
        predicted = solve_fn(img)
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
        
        if predicted and len(predicted) == 7:
            for a, b in zip(predicted, expected):
                if a == b:
                    char_correct += 1
                char_total += 1
            if predicted == expected:
                captcha_correct += 1
    
    avg = sum(times) / len(times)
    char_acc = char_correct / char_total * 100 if char_total else 0
    captcha_acc = captcha_correct / len(data) * 100
    p50 = sorted(times)[len(times)//2]
    p99 = sorted(times)[int(len(times)*0.99)]
    print(f"  {name:15s}  {avg:6.1f}ms  p50={p50:.0f}ms  p99={p99:.0f}ms  "
          f"char={char_acc:.1f}%  captcha={captcha_acc:.1f}%")
    return avg, char_acc, captcha_acc

# ── PyTorch (batch 7) ──
def solve_pt_batch(img):
    chars = segment_captcha(img)
    if len(chars) != 7:
        return ""
    batch = np.array([normalize_char(c) for c in chars], dtype=np.float32)
    batch_t = torch.from_numpy(np.expand_dims(batch, 1)).to(device)
    with torch.no_grad():
        outputs = pt_model(batch_t)
        _, preds = outputs.max(1)
    return ''.join(IDX_TO_CHAR[p.item()] for p in preds)

# ── PyTorch (loop 1 char at a time) ──
def solve_pt_loop(img):
    chars = segment_captcha(img)
    if len(chars) != 7:
        return ""
    pred = ""
    for ci in chars:
        norm = normalize_char(ci)
        t = torch.from_numpy(norm).float().unsqueeze(0).unsqueeze(0).to(device)
        with torch.no_grad():
            o = pt_model(t)
            _, p = o.max(1)
        pred += IDX_TO_CHAR[p.item()]
    return pred

# ── TorchScript traced (batch) ──
def solve_ts_batch(img):
    chars = segment_captcha(img)
    if len(chars) != 7:
        return ""
    batch = np.array([normalize_char(c) for c in chars], dtype=np.float32)
    batch_t = torch.from_numpy(np.expand_dims(batch, 1)).to(device)
    outputs = ts_traced(batch_t)
    _, preds = outputs.max(1)
    return ''.join(IDX_TO_CHAR[p.item()] for p in preds)

# ── ONNX Runtime (batch) ──
def solve_onnx(img):
    chars = segment_captcha(img)
    if len(chars) != 7:
        return ""
    batch = np.array([normalize_char(c) for c in chars], dtype=np.float32)
    batch = np.expand_dims(batch, 1)  # (7, 1, 32, 32)
    outputs = ort_session.run(['output'], {'input': batch})
    probs = torch.from_numpy(outputs[0]).softmax(dim=1)
    _, preds = probs.max(1)
    return ''.join(IDX_TO_CHAR[p.item()] for p in preds)

# ── TorchScript scripted (batch) ──
def solve_ts_script(img):
    chars = segment_captcha(img)
    if len(chars) != 7:
        return ""
    batch = np.array([normalize_char(c) for c in chars], dtype=np.float32)
    batch_t = torch.from_numpy(np.expand_dims(batch, 1)).to(device)
    outputs = ts_model(batch_t)
    _, preds = outputs.max(1)
    return ''.join(IDX_TO_CHAR[p.item()] for p in preds)


print(f"  {'Backend':15s}  {'Avg':>6s}  {'Latency':>10s}  {'Accuracy':>20s}")
print(f"  {'-'*15}  {'-'*6}  {'-'*10}  {'-'*20}")

# Run benchmarks
results = []
results.append(("PyTorch batch", *run_benchmark("PyTorch batch", solve_pt_batch, test_data)))
results.append(("PyTorch loop", *run_benchmark("PyTorch loop", solve_pt_loop, test_data)))
results.append(("TorchScript", *run_benchmark("TorchScript", solve_ts_batch, test_data)))
results.append(("ONNX FP32", *run_benchmark("ONNX FP32", solve_onnx, test_data)))
results.append(("TS scripted", *run_benchmark("TS scripted", solve_ts_script, test_data)))

print()
print("=" * 60)
print("SUMMARY — Speedup vs PyTorch loop (baseline)")
print("=" * 60)
baseline = results[1][1]  # PyTorch loop time
for name, avg, char_acc, captcha_acc in results:
    speedup = baseline / avg
    print(f"  {name:15s}  {avg:6.1f}ms  {speedup:5.1f}x  char={char_acc:.1f}%")
