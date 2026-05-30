"""Analyze confusion matrix of current CNN model."""
import sys
sys.path.insert(0, 'captcha_solver_imss')
from pathlib import Path
from cnn_solver.train_v2 import segment_captcha, normalize_char, CHAR_TO_IDX, IDX_TO_CHAR
from cnn_solver.model_v2 import create_model
import torch
import torch.nn.functional as F
import cv2
from collections import Counter

device = torch.device('cpu')
model_path = Path('captcha_solver_imss/cnn_solver/models/attention_s42_409_v4.pt')
cp = torch.load(model_path, map_location=device, weights_only=False)
model = create_model(cp['arch'], num_classes=62).to(device)
model.load_state_dict(cp['model_state_dict'])
model.eval()

samples_dir = Path('captcha_solver_imss/test_samples')
captchas = []
for f in samples_dir.iterdir():
    if f.suffix not in ('.jpg', '.PNG'):
        continue
    label = f.stem.split('_')[0]
    if len(label) == 7 and all(c in CHAR_TO_IDX for c in label):
        captchas.append((f, label))

confusion = Counter()
char_correct = 0
char_total = 0
by_char = {}
times = []

for img_path, expected in captchas:
    import time
    img = cv2.imread(str(img_path))
    if img is None:
        continue
    chars = segment_captcha(img)
    if len(chars) != 7:
        continue

    start = time.time()
    for ci, exp_char in zip(chars, expected):
        norm = normalize_char(ci)
        t = torch.from_numpy(norm).float().unsqueeze(0).unsqueeze(0).to(device)
        o = model(t)
        probs = F.softmax(o, dim=1)
        conf, pred = probs.max(1)
        pred_char = IDX_TO_CHAR[pred.item()]

        if exp_char not in by_char:
            by_char[exp_char] = {
                'correct': 0, 'total': 0,
                'confusions': Counter(), 'avg_conf': 0.0
            }

        by_char[exp_char]['total'] += 1
        by_char[exp_char]['avg_conf'] += conf.item()

        if pred_char == exp_char:
            char_correct += 1
            by_char[exp_char]['correct'] += 1
        else:
            confusion[(exp_char, pred_char)] += 1
            by_char[exp_char]['confusions'][pred_char] += 1
        char_total += 1
    times.append((time.time() - start) * 1000)

for c in by_char:
    d = by_char[c]
    d['avg_conf'] /= d['total']
    d['acc'] = d['correct'] / d['total'] * 100

avg_ms = sum(times) / len(times)

print(f'=== OVERALL ===')
print(f'Char acc: {char_correct}/{char_total} = {char_correct/char_total*100:.1f}%')
print(f'Avg time per captcha: {avg_ms:.1f}ms')
print()

# Top confusions
print('=== TOP 15 CONFUSIONS ===')
for (exp, pred), count in confusion.most_common(15):
    print(f'  "{exp}" -> "{pred}": {count}x')
print()

# Worst characters by accuracy (with at least 5 samples)
print('=== WORST CHARACTERS (min 5 samples) ===')
sorted_by_acc = sorted(
    [(c, d) for c, d in by_char.items() if d['total'] >= 5],
    key=lambda x: x[1]['acc']
)
for c, data in sorted_by_acc[:10]:
    top3 = data['confusions'].most_common(3)
    conf_str = ', '.join(f'"{p}"({c}x)' for p, c in top3)
    print(f'  "{c}":  acc={data["acc"]:.0f}%  ({data["correct"]}/{data["total"]})  '
          f'conf={data["avg_conf"]:.3f}  errors: {conf_str}')
print()

# Characters with few samples (1-4)
print('=== LOW SAMPLE CHARACTERS (1-4 samples) ===')
low = [(c, d) for c, d in by_char.items() if d['total'] < 5]
for c, data in sorted(low, key=lambda x: x[1]['total']):
    top1 = data['confusions'].most_common(1)
    err = f'  -> "{top1[0][0]}"({top1[0][1]}x)' if top1 else ''
    print(f'  "{c}":  {data["total"]} samples, acc={data["acc"]:.0f}%{err}')
print()

# Missing classes
all_classes = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
found = set(by_char.keys())
missing = [c for c in all_classes if c not in found]
print(f'=== MISSING CLASSES (0 samples) ===')
print(f'  ({len(missing)}): {" ".join(missing)}')
