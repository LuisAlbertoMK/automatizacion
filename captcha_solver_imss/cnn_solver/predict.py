"""
predict.py
Inference: segment captcha → classify each char → return text.

Uses trained CNN model. Falls back gracefully if model not found.
"""
from pathlib import Path
from typing import Optional, List, Tuple

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from .dataset import (
    segment_captcha,
    normalize_char,
    CHAR_TO_IDX,
    IDX_TO_CHAR,
    MODEL_DIR,
    N_CLASSES,
)
from .model import CaptchaCNN


class CNNPredictor:
    """
    Predictor for IMSS captchas using segmentation + CNN classification.

    Loads trained model from cnn_solver/models/best.pt.
    If model not found, all predictions return error state.
    """

    def __init__(self, model_path: Optional[str] = None, device: str = "auto"):
        self.device = torch.device(
            "cuda" if device == "auto" and torch.cuda.is_available()
            else "cpu"
        )
        self.model = None
        self._loaded = False

        path = Path(model_path or MODEL_DIR / "best.pt")
        if path.exists():
            self._load_model(path)
        else:
            print(f"  [CNN] Model not found at {path}. Train first with: "
                  f"py -3.14 -m captcha_solver_imss.cnn_solver.train")

    def _load_model(self, path: Path):
        try:
            checkpoint = torch.load(path, map_location=self.device, weights_only=False)
            self.model = CaptchaCNN(num_classes=N_CLASSES).to(self.device)
            self.model.load_state_dict(checkpoint["model_state_dict"])
            self.model.eval()
            self._loaded = True
            print(f"  [CNN] Model loaded from {path} "
                  f"(epoch {checkpoint.get('epoch', '?')}, "
                  f"val_acc={checkpoint.get('val_acc', '?'):.4f})")
        except Exception as e:
            print(f"  [CNN] Error loading model: {e}")

    @property
    def is_loaded(self) -> bool:
        return self._loaded and self.model is not None

    def predict_char(self, char_img: np.ndarray) -> Tuple[str, float]:
        """
        Classify a single character image.

        Args:
            char_img: (H, W) grayscale or binary image

        Returns:
            (predicted_char, confidence)
        """
        if not self.is_loaded:
            return "?", 0.0

        # Normalize to (32, 32)
        normalized = normalize_char(char_img, target_size=32)

        # Tensor: (1, 1, 32, 32)
        tensor = torch.from_numpy(normalized).float().unsqueeze(0).unsqueeze(0)
        tensor = tensor.to(self.device)

        with torch.no_grad():
            outputs = self.model(tensor)
            probs = F.softmax(outputs, dim=1)
            conf, pred = torch.max(probs, dim=1)

        char = IDX_TO_CHAR[pred.item()]
        confidence = conf.item()
        return char, confidence

    def predict(self, img: np.ndarray) -> dict:
        """
        Predict entire captcha text from image.

        Args:
            img: (H, W, 3) BGR captcha image

        Returns:
            dict with: value, confidence, char_confidences, success
        """
        if not self.is_loaded:
            return {
                "value": "",
                "confidence": 0.0,
                "char_confidences": [],
                "success": False,
                "error": "Model not loaded",
            }

        # Segment into characters
        chars = segment_captcha(img, expected_len=7)

        if len(chars) != 7:
            return {
                "value": "",
                "confidence": 0.0,
                "char_confidences": [],
                "success": False,
                "error": f"Segmentation failed: got {len(chars)} chars, expected 7",
            }

        # Classify each character
        text = ""
        confs = []
        for char_img in chars:
            char, conf = self.predict_char(char_img)
            text += char
            confs.append(conf)

        avg_conf = sum(confs) / len(confs) if confs else 0.0
        min_conf = min(confs) if confs else 0.0
        success = min_conf >= 0.3 or avg_conf >= 0.5  # Tuned threshold

        return {
            "value": text,
            "confidence": avg_conf,
            "min_confidence": min_conf,
            "char_confidences": confs,
            "n_chars": len(text),
            "success": success,
            "error": None,
        }


# ── Integration helper ──────────────────────────────────────────────

def segment_and_classify(
    image_source,
    model_path: Optional[str] = None,
    device: str = "auto",
) -> dict:
    """
    Convenience function: load image → segment → classify → return result.

    Args:
        image_source: path (str/Path), bytes, or numpy array
        model_path: optional path to model checkpoint

    Returns:
        dict with prediction results
    """
    from ..preprocess import load_image as load_img

    if isinstance(image_source, np.ndarray):
        img = image_source
    else:
        img = load_img(image_source)

    if img is None:
        return {
            "value": "",
            "confidence": 0.0,
            "success": False,
            "error": "Could not load image",
        }

    predictor = CNNPredictor(model_path=model_path, device=device)
    return predictor.predict(img)
