"""
model_v2.py
Arquitecturas CNN mejoradas para captcha IMSS (62 clases, mixed case).

Opción A: WideCNN — más ancha que la original (~2.5M params)
  - 64→128→256→512 filters (vs 32→64→128→256)
  - Extra Conv block (5 conv layers vs 4)
  - Más FC: 2048→512→256→62
  - Inference: ~5-8ms en CPU

Opción B: ResNet-like — bloques residuales (~1.8M params)
  - 3 bloques residuales con skip connections
  - Mejor para datasets chicos (gradient flow)
  - Inference: ~5-8ms en CPU

Opción C: AttentionCNN — atención espacial (~1.2M params)
  - Same as original + spatial attention modules
  - Ayuda a enfocarse en el caracter vs ruido
  - Inference: ~3-5ms en CPU
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


def count_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


# ═══════════════════════════════════════════════════════════════════════════
# Opción A: WideCNN
# ═══════════════════════════════════════════════════════════════════════════

class WideCNN(nn.Module):
    """
    CNN más ancha y profunda.
    5 conv layers con filtros crecientes: 64→128→256→512→512
    Input: (1, 32, 32) → Output: num_classes
    """
    def __init__(self, num_classes: int = 62, dropout: float = 0.4):
        super().__init__()

        self.features = nn.Sequential(
            # Conv1: 1 → 64
            nn.Conv2d(1, 64, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 64×16×16

            # Conv2: 64 → 128
            nn.Conv2d(64, 128, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 128×8×8

            # Conv3: 128 → 256
            nn.Conv2d(128, 256, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 256×4×4

            # Conv4: 256 → 512
            nn.Conv2d(256, 512, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(512),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 512×2×2

            # Conv5: 512 → 512 (extra depth)
            nn.Conv2d(512, 512, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(512),
            nn.ReLU(inplace=True),
            # No maxpool — tamaño se mantiene 512×2×2
        )

        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(512 * 2 * 2, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout * 0.75),
            nn.Linear(512, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout * 0.5),
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


# ═══════════════════════════════════════════════════════════════════════════
# Opción B: ResidualCNN (ResNet-style)
# ═══════════════════════════════════════════════════════════════════════════

class ResidualBlock(nn.Module):
    """Basic residual block: Conv → BN → ReLU → Conv → BN → +skip → ReLU"""
    def __init__(self, channels, kernel_size=3, dropout=0.0):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size, padding=kernel_size//2, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size, padding=kernel_size//2, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)
        self.dropout = nn.Dropout2d(dropout) if dropout > 0 else nn.Identity()

    def forward(self, x):
        identity = x
        out = self.conv1(x)
        out = self.bn1(out)
        out = F.relu(out, inplace=True)
        out = self.dropout(out)
        out = self.conv2(out)
        out = self.bn2(out)
        out += identity  # skip connection
        out = F.relu(out, inplace=True)
        return out


class ResidualCNN(nn.Module):
    """
    CNN con 3 bloques residuales.
    Input: (1, 32, 32) → Output: num_classes
    """
    def __init__(self, num_classes: int = 62, dropout: float = 0.3):
        super().__init__()

        # Stem: 1 → 64
        self.stem = nn.Sequential(
            nn.Conv2d(1, 64, kernel_size=5, padding=2, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 64×16×16
        )

        # Residual blocks (with downsampling between them)
        self.layer1 = nn.Sequential(
            ResidualBlock(64, dropout=dropout),
            ResidualBlock(64, dropout=dropout),
        )

        self.down1 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
        )  # 128×8×8

        self.layer2 = nn.Sequential(
            ResidualBlock(128, dropout=dropout),
            ResidualBlock(128, dropout=dropout),
        )

        self.down2 = nn.Sequential(
            nn.Conv2d(128, 256, kernel_size=3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
        )  # 256×4×4

        self.layer3 = nn.Sequential(
            ResidualBlock(256, dropout=dropout),
            ResidualBlock(256, dropout=dropout),
        )

        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(256, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout * 0.5),
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        x = self.stem(x)
        x = self.layer1(x)
        x = self.down1(x)
        x = self.layer2(x)
        x = self.down2(x)
        x = self.layer3(x)
        x = self.classifier(x)
        return x


# ═══════════════════════════════════════════════════════════════════════════
# OriginalCNN (same as CaptchaCNN in model.py, for compatibility)
# ═══════════════════════════════════════════════════════════════════════════

class OriginalCNN(nn.Module):
    """Same architecture as CaptchaCNN from model.py — proven 75.2%"""
    def __init__(self, num_classes: int = 62, dropout: float = 0.5):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(32),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(64),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(128),
            nn.MaxPool2d(2),
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(256),
            nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(256 * 2 * 2, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout * 0.6),
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


# ═══════════════════════════════════════════════════════════════════════════
# AttentionCNN (espacial)
# ═══════════════════════════════════════════════════════════════════════════

class SpatialAttention(nn.Module):
    """Spatial attention: conv1×1 → sigmoid → multiply"""
    def __init__(self, channels):
        super().__init__()
        self.conv = nn.Conv2d(channels, 1, kernel_size=1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        attn = self.conv(x)
        attn = self.sigmoid(attn)
        return x * attn


class AttentionCNN(nn.Module):
    """
    CNN con módulos de atención espacial después de cada conv block.
    Ayuda a que el modelo se enfoque en el caracter vs el fondo.
    Input: (1, 32, 32) → Output: num_classes
    """
    def __init__(self, num_classes: int = 62, dropout: float = 0.4):
        super().__init__()

        self.features = nn.Sequential(
            # Block 1
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(32),
            nn.MaxPool2d(2),  # 32×16×16
            SpatialAttention(32),

            # Block 2
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(64),
            nn.MaxPool2d(2),  # 64×8×8
            SpatialAttention(64),

            # Block 3
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(128),
            nn.MaxPool2d(2),  # 128×4×4
            SpatialAttention(128),

            # Block 4
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(256),
            nn.MaxPool2d(2),  # 256×2×2
            SpatialAttention(256),
        )

        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(256 * 2 * 2, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout * 0.6),
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


# ═══════════════════════════════════════════════════════════════════════════
# Ensemble inference
# ═══════════════════════════════════════════════════════════════════════════

class EnsembleModel:
    """
    Ensemble de N modelos. Voting por mayoría + fallback a max confidence.
    """
    def __init__(self, models: list):
        assert len(models) > 0, "Need at least 1 model"
        self.models = models

    @torch.no_grad()
    def predict(self, x: torch.Tensor) -> tuple:
        """
        Args:
            x: (B, 1, 32, 32) tensor
        Returns:
            (predicted_class, confidence, all_probs)
        """
        all_probs = []
        for model in self.models:
            model.eval()
            outputs = model(x)
            probs = F.softmax(outputs, dim=1)
            all_probs.append(probs)

        # Average probabilities (better than voting for small ensembles)
        avg_probs = torch.stack(all_probs).mean(dim=0)
        conf, pred = torch.max(avg_probs, dim=1)
        return pred.item(), conf.item(), avg_probs

    def to(self, device):
        for m in self.models:
            m.to(device)
        return self

    def eval(self):
        for m in self.models:
            m.eval()


# ═══════════════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════════════

def create_model(arch: str = "wide", num_classes: int = 62,
                 dropout: float = 0.4) -> nn.Module:
    """
    Factory para crear modelos por nombre.

    Args:
        arch: "wide" | "residual" | "attention"
        num_classes: número de clases (default 62)
        dropout: dropout rate
    """
    archs = {
        "original": OriginalCNN,
        "wide": WideCNN,
        "residual": ResidualCNN,
        "attention": AttentionCNN,
    }
    if arch not in archs:
        raise ValueError(f"Unknown architecture: {arch}. Choices: {list(archs.keys())}")

    model = archs[arch](num_classes=num_classes, dropout=dropout)
    return model


# ═══════════════════════════════════════════════════════════════════════════
# CLI test
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    for name in ["original", "wide", "residual", "attention"]:
        model = create_model(name)
        params = count_params(model)
        x = torch.randn(7, 1, 32, 32)  # batch of 7 chars
        y = model(x)
        print(f"{name:10s} | params={params:>7,} | input={list(x.shape)} | output={list(y.shape)}")

        # Timming
        import time
        model.eval()
        with torch.no_grad():
            start = time.time()
            for _ in range(100):
                model(x)
            elapsed = (time.time() - start) / 100 * 1000
            print(f"{'':10s} | batch_infer={elapsed:.1f}ms for 7 chars "
                  f"({elapsed/7:.2f}ms/char)")
        print()
