"""
solver_v2.py
CNN solver mejorado con soporte para todas las arquitecturas y ensemble.

Características:
  - Soporta WideCNN, ResidualCNN, AttentionCNN (model_v2.py)
  - Ensemble de N modelos con votación por avg probabilities
  - Batch inference (procesa 7 chars en paralelo)
  - ONNX Runtime (3x más rápido) cuando está disponible
  - Auto-selección del mejor modelo disponible
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import numpy as np

if TYPE_CHECKING:
    pass

# ONNX Runtime opcional
try:
    import onnxruntime as _ort
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False


class CNNSolverV2:
    """
    CNN solver v2 con soporte para ONNX, ensemble y todas las arquitecturas.

    Uso:
        solver = CNNSolverV2()
        result = solver.solve(img)

        # O con ensemble:
        solver = CNNSolverV2(model_paths=["...pt", "...pt", "...pt"])
    """

    def __init__(self, model_paths: Optional[List[str]] = None,
                 device: str = "auto", verbose: bool = True,
                 use_onnx: bool = True):
        self._torch = None
        self._F = None
        self._device_str = device
        self.device = None
        self.verbose = verbose
        self.use_onnx = use_onnx and HAS_ONNX
        self.models = []        # PyTorch models (fallback / ensemble)
        self.ort_sessions = []  # ONNX Runtime sessions (single model)
        self._loaded = False
        self._is_ensemble = False

        if model_paths:
            self._load_models(model_paths)
        else:
            self._load_best()

        engine = "ONNX" if self.ort_sessions else \
                 f"Ensemble({len(self.models)})" if self._is_ensemble else \
                 "PyTorch"
        self._log(f"CNNSolverV2 listo "
                  f"[{'OK' if self._loaded else 'NO MODEL'}] "
                  f"({engine}, {len(self.models)} model(s))")

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

    # ── Loading ───────────────────────────────────────────────

    def _load_best(self):
        """Auto-select best model from model directory."""
        from .train_v2 import MODEL_DIR
        # Priority: v4 (latest, 409 captchas) > v3_full > v3 > attention > wide > residual > original
        pattern_order = [
            ("*v4*", "attention"),       # v4 — newest (409 captchas)
            ("*v3_full*", "attention"),  # v3 full data
            ("*v3*", "attention"),       # v3 with validation
            ("attention*", "attention"), # attention
            ("wide*", "wide"),           # wide
            ("residual*", "residual"),   # residual
            ("best_v2*", "original"),    # original train_v2
            ("best*", "original"),       # original train
        ]

        winning_pattern = None
        best_paths = []
        best_arch = "original"

        for pattern, arch in pattern_order:
            matches = sorted(MODEL_DIR.glob(pattern))
            # Filter to only .pt files
            pt_matches = [m for m in matches if m.suffix == '.pt']
            if pt_matches:
                best_paths = [pt_matches[-1]]  # newest
                best_arch = arch
                winning_pattern = pattern
                break

        if not best_paths:
            self._log("No models found")
            return

        # Check for ensemble candidates — ONLY for winning pattern
        # (e.g. if *v4* won, only look for more *v4* models for ensemble)
        if winning_pattern:
            ensemble_matches = sorted(MODEL_DIR.glob(winning_pattern))
            ensemble_pt = [m for m in ensemble_matches if m.suffix == '.pt']
            if len(ensemble_pt) >= 2:
                ensemble_paths = ensemble_pt[-3:]
                self._log(f"Ensemble found: {[p.name for p in ensemble_paths]}")
                self._load_models([str(p) for p in ensemble_paths])
                return

        # Single model
        self._load_models([str(best_paths[0])])

    def _load_models(self, paths: List[str]):
        """Load multiple models. Single model → try ONNX; multiple → ensemble."""
        from .model_v2 import create_model
        from .train_v2 import N_CLASSES
        loaded = []
        self.ort_sessions = []

        for path_str in paths:
            path = Path(path_str)
            if not path.exists():
                self._log(f"Model not found: {path}")
                continue

            try:
                checkpoint = self.torch.load(path, map_location=self.device,
                                        weights_only=False)
                arch = checkpoint.get("arch", "original")
                seed = checkpoint.get("seed", "?")

                model = create_model(arch, num_classes=N_CLASSES).to(self.device)
                model.load_state_dict(checkpoint["model_state_dict"])
                model.eval()
                loaded.append(model)

                val_acc = checkpoint.get("val_acc",
                           checkpoint.get("captcha_acc", "?"))
                self._log(f"Loaded {path.name} "
                          f"(arch={arch}, seed={seed}, val={val_acc})")

                # Try ONNX export for this model (single model only)
                onnx_path = path.with_suffix('.onnx')
                if self.use_onnx and len(paths) == 1 and not onnx_path.exists():
                    self._export_onnx(model, onnx_path, arch)
                if self.use_onnx and len(paths) == 1 and onnx_path.exists():
                    try:
                        sess = _ort.InferenceSession(
                            str(onnx_path), providers=['CPUExecutionProvider']
                        )
                        self.ort_sessions.append(sess)
                        self._log(f"ONNX session ready: {onnx_path.name}")
                    except Exception as e:
                        self._log(f"ONNX load failed: {e}")

            except Exception as e:
                self._log(f"Error loading {path.name}: {e}")

        if not loaded:
            self._loaded = False
            return

        self.models = loaded
        self._loaded = True
        self._is_ensemble = len(loaded) > 1 and not self.ort_sessions
        if self._is_ensemble:
            self._log(f"Ensemble: {len(loaded)} models")

    # ── ONNX export ───────────────────────────────────────────

    def _export_onnx(self, model, onnx_path: Path, arch: str):
        """Export PyTorch model to ONNX for faster inference."""
        try:
            dummy = self.torch.randn(7, 1, 32, 32)
            self.torch.onnx.export(
                model, dummy, onnx_path,
                input_names=['input'], output_names=['output'],
                dynamic_axes={'input': {0: 'batch'}, 'output': {0: 'batch'}},
                opset_version=17, verbose=False,
            )
            self._log(f"ONNX exported: {onnx_path.name} "
                      f"({onnx_path.stat().st_size // 1024} KB)")
        except Exception as e:
            self._log(f"ONNX export failed: {e}")

    @property
    def is_loaded(self) -> bool:
        return self._loaded and len(self.models) > 0

    # ── Ensemble helpers ───────────────────────────────────────

    def _ensemble_infer(self, model, batch_t):
        """Run single model inference — designed for thread pool dispatch.

        Args:
            model: PyTorch model in eval mode
            batch_t: Pre-processed batch tensor on self.device

        Returns:
            Softmax probability tensor (batch_size × n_classes)
        """
        with self.torch.no_grad():
            outputs = model(batch_t)
            return self.F.softmax(outputs, dim=1)

    # ── Solve ─────────────────────────────────────────────────

    def solve(self, img: np.ndarray) -> dict:
        """
        Solve captcha from numpy image.

        Args:
            img: (H, W, 3) BGR image

        Returns:
            dict with: value, confidence, char_confidences, success, engine
        """
        from .train_v2 import IDX_TO_CHAR, normalize_char, segment_captcha
        start = time.time()

        if not self.is_loaded:
            return self._error("No model loaded", start)

        # ── Segment ────────────────────────────────────────────
        chars = segment_captcha(img, expected_len=7)
        if len(chars) != 7:
            return self._error(f"Segmentation: {len(chars)} chars", start)

        # ── Batch inference ────────────────────────────────────
        # Normalizar todos los chars y crear batch
        batch = np.array([normalize_char(c) for c in chars], dtype=np.float32)
        batch = np.expand_dims(batch, 1)  # (7, 1, 32, 32)

        # ONNX inference (single model, ~3x faster)
        if self.ort_sessions:
            outputs = self.ort_sessions[0].run(['output'], {'input': batch})
            probs_t = self.torch.from_numpy(outputs[0]).softmax(dim=1)
            confs, preds = probs_t.max(1)
            engine = "CNNv2(ONNX)"
        elif len(self.models) == 1:
            # Single model (PyTorch)
            batch_t = self.torch.from_numpy(batch).to(self.device)
            with self.torch.no_grad():
                outputs = self.models[0](batch_t)
                probs = self.F.softmax(outputs, dim=1)
                confs, preds = probs.max(1)
            engine = "CNNv2"
        else:
            # Ensemble: average probabilities across models in PARALLEL
            # ThreadPoolExecutor funciona porque PyTorch suelta el GIL
            # durante model() en CPU. Para CUDA los kernels se serializan
            # por el default stream, pero el overhead de threads es mínimo.
            batch_t = self.torch.from_numpy(batch).to(self.device)
            with ThreadPoolExecutor(max_workers=len(self.models)) as pool:
                futures = [pool.submit(self._ensemble_infer, m, batch_t)
                           for m in self.models]
                probs_list = [f.result() for f in as_completed(futures)]
            avg_probs = sum(probs_list) / len(self.models)
            confs, preds = avg_probs.max(1)
            engine = f"CNNv2(ensemble={len(self.models)})"

        # Decode
        text = ""
        char_confs = []
        for i in range(7):
            char = IDX_TO_CHAR[preds[i].item()]
            conf = confs[i].item()
            text += char
            char_confs.append(conf)

        avg_conf = sum(char_confs) / 7 if char_confs else 0.0
        min_conf = min(char_confs) if char_confs else 0.0
        elapsed = int((time.time() - start) * 1000)

        if self.verbose:
            self._log(f"'{text}' ({engine}, "
                      f"conf={avg_conf:.3f}, min={min_conf:.3f}, "
                      f"{elapsed}ms)")

        return {
            "success": True,
            "value": text,
            "confidence": avg_conf,
            "min_confidence": min_conf,
            "char_confidences": char_confs,
            "engine": engine,
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

    # ── Helpers ───────────────────────────────────────────────

    def _error(self, msg: str, start: float) -> dict:
        elapsed = int((time.time() - start) * 1000)
        return {
            "success": False,
            "value": "",
            "confidence": 0.0,
            "engine": "CNNv2",
            "error": msg,
            "elapsed_ms": elapsed,
        }

    def _log(self, msg: str):
        if self.verbose:
            print(f"  [CNN_SolverV2] {msg}")
