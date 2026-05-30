"""
store.py
Persistencia de capturas del CAPTCHA del IMSS.

Guarda cada captura con:
  - UUID único (request_id)
  - Timestamp ISO
  - Imagen raw (bytes) como PNG
  - Valor resuelto (cuando se logra)
  - Metadatos (size, modo, etc.)
  - Pipeline usado + score

Permite:
  - Re-procesar imágenes guardadas con diferentes configs
  - Exportar dataset etiquetado para entrenamiento
  - Analizar tasa de acierto histórica
"""

import json
import uuid
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict


CAPTCHAS_DIR = Path(__file__).parent / "capturas"
METADATA_FILE = "metadata.json"


@dataclass
class CapturaEntry:
    """Registro de una captura individual."""
    request_id: str
    timestamp: str           # ISO format
    filename: str            # nombre del archivo imagen
    image_size: str          # "WxH"
    resolved_value: str      # valor del CAPTCHA cuando se resolvió
    pipeline_used: str       # "ensemble", "easyocr", "tesseract"
    score: float             # confianza 0-1
    elapsed_ms: int          # ms que tomó resolverlo
    correct: Optional[bool]  # None = sin etiquetar


class CaptchaStore:
    """
    Almacena y gestiona capturas del CAPTCHA del IMSS.

    Cada captura se guarda como PNG en capturas/ y su metadata
    se persiste en capturas/metadata.json.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or CAPTCHAS_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_file = self.base_dir / METADATA_FILE
        self._metadata: dict[str, CapturaEntry] = {}
        self._load_metadata()

    # ── Público ───────────────────────────────────────────────────

    def save_capture(self, image_bytes: bytes, request_id: Optional[str] = None) -> str:
        """
        Guarda una imagen de CAPTCHA.

        Args:
            image_bytes: Raw bytes de la imagen
            request_id: UUID opcional (se genera uno si no se provee)

        Returns:
            request_id asignado
        """
        rid = request_id or uuid.uuid4().hex[:12]
        ts = datetime.now(timezone.utc).isoformat()

        # Guardar PNG
        filename = f"{rid}.png"
        img_path = self.base_dir / filename
        img_path.write_bytes(image_bytes)

        # Detectar tamaño
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(image_bytes))
            size_str = f"{img.width}x{img.height}"
        except Exception:
            size_str = "desconocido"

        entry = CapturaEntry(
            request_id=rid,
            timestamp=ts,
            filename=filename,
            image_size=size_str,
            resolved_value="",
            pipeline_used="",
            score=0.0,
            elapsed_ms=0,
            correct=None,
        )

        self._metadata[rid] = entry
        self._save_metadata()
        return rid

    def update_result(self, request_id: str, value: str,
                      pipeline: str, score: float, elapsed_ms: int):
        """Actualiza el resultado de una captura."""
        entry = self._metadata.get(request_id)
        if entry:
            entry.resolved_value = value
            entry.pipeline_used = pipeline
            entry.score = score
            entry.elapsed_ms = elapsed_ms
            self._save_metadata()

    def label_correct(self, request_id: str, expected_value: str):
        """
        Etiqueta una captura como correcta o incorrecta.

        Útil para: después de enviar el CAPTCHA y saber si el portal
        lo aceptó o lo rechazó.
        """
        entry = self._metadata.get(request_id)
        if entry:
            entry.correct = (entry.resolved_value == expected_value)
            self._save_metadata()

    def get_all_entries(self) -> list[CapturaEntry]:
        """Retorna todas las entradas ordenadas por timestamp."""
        entries = sorted(
            self._metadata.values(),
            key=lambda e: e.timestamp,
            reverse=True,
        )
        return entries

    def get_entry(self, request_id: str) -> Optional[CapturaEntry]:
        return self._metadata.get(request_id)

    def get_image_path(self, request_id: str) -> Optional[Path]:
        """Retorna el path de la imagen para un request_id."""
        entry = self._metadata.get(request_id)
        if entry:
            p = self.base_dir / entry.filename
            return p if p.exists() else None
        return None

    def get_image_bytes(self, request_id: str) -> Optional[bytes]:
        """Retorna los bytes de la imagen."""
        p = self.get_image_path(request_id)
        if p:
            return p.read_bytes()
        return None

    def export_dataset(self) -> list[dict]:
        """Exporta dataset completo para análisis/entrenamiento."""
        return [
            {k: v for k, v in asdict(e).items() if v}
            for e in self._metadata.values()
            if e.resolved_value
        ]

    def stats(self) -> dict:
        """Estadísticas de resolución."""
        total = len(self._metadata)
        resolved = sum(1 for e in self._metadata.values() if e.resolved_value)
        labeled = [e for e in self._metadata.values() if e.correct is not None]
        correct = sum(1 for e in labeled if e.correct)
        return {
            "total_capturas": total,
            "resueltas": resolved,
            "etiquetadas": len(labeled),
            "correctas": correct,
            "tasa_acierto": round(correct / len(labeled), 2) if labeled else 0,
        }

    # ── Interno ───────────────────────────────────────────────────

    def _load_metadata(self):
        if self._metadata_file.exists():
            try:
                raw = self._metadata_file.read_text(encoding="utf-8")
                data = json.loads(raw)
                for k, v in data.items():
                    self._metadata[k] = CapturaEntry(**v)
            except Exception:
                self._metadata = {}

    def _save_metadata(self):
        raw = {k: asdict(v) for k, v in self._metadata.items()}
        self._metadata_file.write_text(
            json.dumps(raw, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
