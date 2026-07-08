import torch
cp = torch.load(
    'captcha_solver_imss/cnn_solver/models/attention_s123_409_v4.pt',
    weights_only=False, map_location='cpu'
)
print(f'epoch={cp.get("epoch","?")} arch={cp.get("arch","?")} '
      f'seed={cp.get("seed","?")} '
      f'val={cp.get("val_acc",0):.2f}% '
      f'captcha={cp.get("captcha_acc",0):.2f}% '
      f'phase={cp.get("phase","?")}')
