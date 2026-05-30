"""
model.py
Small CNN classifier for 36-character captcha recognition.

Architecture:
  Input (1, 32, 32)
  Conv1: 32×3×3 → ReLU → BN → MaxPool 2×2  → (32, 16, 16)
  Conv2: 64×3×3 → ReLU → BN → MaxPool 2×2  → (64, 8, 8)
  Conv3: 128×3×3 → ReLU → BN → MaxPool 2×2 → (128, 4, 4)
  Conv4: 256×3×3 → ReLU → BN → MaxPool 2×2 → (256, 2, 2)
  Dropout(0.5)
  FC: 256*2*2 → 256 → ReLU → Dropout(0.3)
  FC: 256 → 36

Total params: ~680K. Inference <1ms on CPU.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


class CaptchaCNN(nn.Module):
    def __init__(self, num_classes: int = 36, dropout: float = 0.5):
        super().__init__()

        self.features = nn.Sequential(
            # Conv1: 1 → 32
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(32),
            nn.MaxPool2d(2),  # 32×16×16

            # Conv2: 32 → 64
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(64),
            nn.MaxPool2d(2),  # 64×8×8

            # Conv3: 64 → 128
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(128),
            nn.MaxPool2d(2),  # 128×4×4

            # Conv4: 128 → 256
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(256),
            nn.MaxPool2d(2),  # 256×2×2
        )

        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(256 * 2 * 2, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout * 0.6),  # 0.3
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


def count_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == "__main__":
    model = CaptchaCNN()
    print(f"Model params: {count_params(model):,}")
    x = torch.randn(1, 1, 32, 32)
    y = model(x)
    print(f"Input: {x.shape}, Output: {y.shape}")
