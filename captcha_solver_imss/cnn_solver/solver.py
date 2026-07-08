"""
cnn_solver/solver.py
Wrapper that integrates the CNN model into the captcha solver pipeline.

Pipeline:
  1. CNN primary (fast, ~2ms, ~75% accuracy)
  2. EasyOCR fallback (slow, ~7s, handles edge cases)
"""
import time
import numpy as np

from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import torch
    import torch.nn.functional as F


class CNNSolver:
    """
    CNN-based captcha solver.
    Segments captcha → classifies each char → returns text with confidence.
    """

    def __init__(self, model_path: Optional[str] = None, device: str = "auto", verbose: bool = True):
        self._torch = None
        self._F = None
        self._device_str = device
        self.device = None
        self.verbose = verbose
        self.model = None
        self._loaded = False
        self._load(model_path)
        self._log(f"CNNSolver listo [{'OK' if self._loaded else 'NO MODEL'}]")

    @property
    def torch(self):
        if self._torch is None:
            import torch
            import torch.nn.functional as F
            self._torch = torch
            self._F = F
            self.device = torch.device(
                "cuda" if self._device_str == "auto" and torch.cuda.is_available() else "cpu"
            )
        return self._torch

    @property
    def F(self):
        if self._F is None:
            _ = self.torch
        return self._F

    def _load(self, model_path: Optional[str]):
        from .model import CaptchaCNN
        from .train_v2 import N_CLASSES, MODEL_DIR
        path = Path(model_path or MODEL_DIR / "best_v2.pt")
        if not path.exists():
            path = MODEL_DIR / "best.pt"
        if not path.exists():
            self._log(f"Modelo no encontrado en {MODEL_DIR}")
            return

        try:
            checkpoint = self.torch.load(path, map_location=self.device, weights_only=False)
            self.model = CaptchaCNN(num_classes=N_CLASSES).to(self.device)
            self.model.load_state_dict(checkpoint["model_state_dict"])
            self.model.eval()
            self._loaded = True
            acc = checkpoint.get("captcha_acc", "?")
            self._log(f"Modelo cargado: {path.name} (captcha_acc={acc}%)")
        except Exception as e:
            self._log(f"Error cargando modelo: {e}")

    @property
    def is_loaded(self) -> bool:
        return self._loaded and self.model is not None

    def solve(self, img: np.ndarray) -> dict:
        """
        Solve captcha from numpy image.

        Args:
            img: (H, W, 3) BGR image

        Returns:
            dict with: value, confidence, char_confidences, success
        """
        from .train_v2 import segment_captcha, normalize_char, IDX_TO_CHAR
        start = time.time()

        if not self.is_loaded:
            elapsed = int((time.time() - start) * 1000)
            return {
                "success": False,
                "value": "",
                "confidence": 0.0,
                "engine": "CNN",
                "error": "Model not loaded",
                "elapsed_ms": elapsed,
            }

        # Segment
        chars = segment_captcha(img, expected_len=7)
        if len(chars) != 7:
            elapsed = int((time.time() - start) * 1000)
            return {
                "success": False,
                "value": "",
                "confidence": 0.0,
                "engine": "CNN",
                "error": f"Segmentation: got {len(chars)} chars",
                "elapsed_ms": elapsed,
            }

        # Classify each char
        text = ""
        confs = []
        char_details = []

        for i, char_img in enumerate(chars):
            norm = normalize_char(char_img)
            tensor = self.torch.from_numpy(norm).float().unsqueeze(0).unsqueeze(0).to(self.device)

            with self.torch.no_grad():
                outputs = self.model(tensor)
                probs = self.F.softmax(outputs, dim=1)
                conf, pred = self.torch.max(probs, dim=1)

            char = IDX_TO_CHAR[pred.item()]
            confidence = conf.item()
            text += char
            confs.append(confidence)
            char_details.append({
                "char": char,
                "confidence": confidence,
                "position": i,
            })

        avg_conf = sum(confs) / len(confs) if confs else 0.0
        min_conf = min(confs) if confs else 0.0
        elapsed = int((time.time() - start) * 1000)

        # CNN always returns success if it got 7 chars
        # (the confidence is informational — EasyOCR fallback is worse)
        success = len(text) == 7

        if self.verbose:
            status = "[OK]" if success else "[LOW]"
            self._log(f"{status} CNN: '{text}' "
                      f"(conf={avg_conf:.3f}, min={min_conf:.3f}, {elapsed}ms)")

        return {
            "success": success,
            "value": text,
            "confidence": avg_conf,
            "min_confidence": min_conf,
            "char_confidences": confs,
            "char_details": char_details,
            "engine": "CNN",
            "n_chars": len(text),
            "elapsed_ms": elapsed,
            "error": None,
        }

    def solve_from_path(self, path: str) -> dict:
        import cv2
        img = cv2.imread(path)
        if img is None:
            return {"success": False, "error": f"Cannot read {path}"}
        return self.solve(img)

    def _log(self, msg: str):
        if self.verbose:
            print(f"  [CNN_Solver] {msg}")
