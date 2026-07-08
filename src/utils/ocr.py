"""
utils/ocr.py
Extracción de texto de imágenes y PDFs usando OCR (Tesseract)

Funcionalidades:
  - Extraer texto de imágenes (PNG, JPG, etc.)
  - Extraer texto de PDFs (convierte a imagen primero)
  - Extraer datos específicos (CURP, NSS, nombres, fechas)
  - Preprocesamiento de imágenes para mejor precisión
"""

import hashlib
import io
import os
import re
from typing import Dict, List, Optional

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

from src.exceptions import OCRError

# Configurar ruta de Tesseract en Windows
# Si está instalado en la ruta por defecto
TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\Public\Tesseract-OCR\tesseract.exe",
]

for path in TESSERACT_PATHS:
    if os.path.exists(path):
        pytesseract.pytesseract.tesseract_cmd = path
        break


class OCRExtractor:
    """Extractor de texto usando OCR con Tesseract."""

    def __init__(self, cache_size: int = 128):
        self._verify_tesseract()
        self._cache: Dict[str, str] = {}
        self._cache_order: List[str] = []
        self._max_cache = max(cache_size, 1)

    def _cache_result(self, key: str, result: str) -> str:
        """Guarda resultado en caché LRU."""
        if key in self._cache:
            self._cache_order.remove(key)
        elif len(self._cache) >= self._max_cache:
            oldest = self._cache_order.pop(0)
            self._cache.pop(oldest, None)
        self._cache[key] = result
        self._cache_order.append(key)
        return result

    def _verify_tesseract(self):
        """Verifica que Tesseract está instalado."""
        try:
            pytesseract.get_tesseract_version()
            print("  [OCR] Tesseract disponible [OK]")
        except Exception:
            print("  [OCR] [!] Tesseract no encontrado. Instálalo desde:")
            print("  https://github.com/UB-Mannheim/tesseract/wiki")
            print("  O el OCR funcionará en modo limitado")

    def extract_from_image(self, image_path: str, lang: str = "spa") -> str:
        """
        Extrae texto de una imagen.
        
        Args:
            image_path: Ruta a la imagen
            lang: Idioma ('spa' para español, 'eng' para inglés)
        
        Returns:
            Texto extraído
        """
        try:
            with Image.open(image_path) as img:
                # Preprocesar imagen para mejor OCR
                img = self._preprocess_image(img)
                text = pytesseract.image_to_string(img, lang=lang)
                return text.strip()
        except Exception as e:
            raise OCRError(f"Error extrayendo texto de imagen: {e}")

    def extract_from_bytes(self, image_bytes: bytes, lang: str = "spa") -> str:
        """
        Extrae texto de bytes de imagen.
        
        Args:
            image_bytes: Bytes de la imagen
            lang: Idioma
        
        Returns:
            Texto extraído
        """
        cache_key = hashlib.sha256(image_bytes).hexdigest()[:16] + "|" + lang
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                img = self._preprocess_image(img)
                text = pytesseract.image_to_string(img, lang=lang)
                return self._cache_result(cache_key, text.strip())
        except Exception as e:
            raise OCRError(f"Error extrayendo texto de bytes: {e}")

    def extract_from_pdf(self, pdf_path: str, lang: str = "spa") -> str:
        """
        Extrae texto de un PDF usando OCR.
        Convierte cada página a imagen y extrae el texto.
        
        Args:
            pdf_path: Ruta al PDF
            lang: Idioma
        
        Returns:
            Texto extraído de todas las páginas
        """
        try:
            try:
                cache_key = f"pdf:{pdf_path}:{lang}:{os.path.getmtime(pdf_path)}"
                cached = self._cache.get(cache_key)
                if cached is not None:
                    return cached
            except OSError:
                cache_key = ""  # archivo no existe aún → sin cache
            from pdf2image import convert_from_path

            # Convertir PDF a imágenes
            images = convert_from_path(pdf_path, dpi=150)

            all_text = []
            for i, img in enumerate(images):
                print(f"  [OCR] Procesando página {i+1}/{len(images)}...")
                img = self._preprocess_image(img)
                text = pytesseract.image_to_string(img, lang=lang)
                all_text.append(text)

            result = "\n\n".join(all_text).strip()
            if cache_key:
                return self._cache_result(cache_key, result)
            return result
        except ImportError:
            raise OCRError(
                "pdf2image no está instalado. Instálalo con: pip install pdf2image\n"
                "También necesitas poppler: https://github.com/oschwartz10612/poppler-windows/releases/"
            )
        except Exception as e:
            raise OCRError(f"Error extrayendo texto de PDF: {e}")

    def _preprocess_image(self, img: Image.Image) -> Image.Image:
        """
        Preprocesa la imagen para mejorar la precisión del OCR.
        
        Args:
            img: Imagen PIL
        
        Returns:
            Imagen preprocesada
        """
        # Convertir a escala de grises
        img = img.convert('L')

        # Aumentar contraste
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # Aumentar nitidez
        img = img.filter(ImageFilter.SHARPEN)

        # Redimensionar: upscale si es muy chica (<1000px), downscale si es muy grande (>2000px)
        width, height = img.size
        if width > 2000:
            scale = 2000 / width
            new_size = (int(width * scale), int(height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        elif 0 < width < 1000:
            scale = 1000 / width
            new_size = (int(width * scale), int(height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        return img

    # -------------------------------------------------------------------------
    # Extractores específicos de datos
    # -------------------------------------------------------------------------

    def extract_curp(self, text: str) -> Optional[str]:
        """
        Extrae CURP del texto.
        
        Args:
            text: Texto donde buscar
        
        Returns:
            CURP encontrada o None
        """
        # Patrón CURP: 4 letras + 6 dígitos + H/M + 5 letras + 1 letra/dígito + 1 dígito
        pattern = r'\b([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b'
        match = re.search(pattern, text.upper())
        return match.group(1) if match else None

    def extract_nss(self, text: str) -> Optional[str]:
        """
        Extrae NSS del texto.
        
        Args:
            text: Texto donde buscar
        
        Returns:
            NSS encontrado o None
        """
        # NSS: 11 dígitos
        pattern = r'\b(\d{11})\b'
        match = re.search(pattern, text)
        return match.group(1) if match else None

    def extract_rfc(self, text: str) -> Optional[str]:
        """
        Extrae RFC del texto.
        
        Args:
            text: Texto donde buscar
        
        Returns:
            RFC encontrado o None
        """
        # RFC: 4 letras + 6 dígitos + 3 caracteres
        pattern = r'\b([A-Z]{4}\d{6}[A-Z0-9]{3})\b'
        match = re.search(pattern, text.upper())
        return match.group(1) if match else None

    def extract_dates(self, text: str) -> List[str]:
        """
        Extrae fechas del texto.
        
        Args:
            text: Texto donde buscar
        
        Returns:
            Lista de fechas encontradas
        """
        patterns = [
            r'\b(\d{2}/\d{2}/\d{4})\b',  # DD/MM/YYYY
            r'\b(\d{2}-\d{2}-\d{4})\b',  # DD-MM-YYYY
            r'\b(\d{4}/\d{2}/\d{2})\b',  # YYYY/MM/DD
            r'\b(\d{4}-\d{2}-\d{2})\b',  # YYYY-MM-DD
        ]

        dates = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            dates.extend(matches)

        return dates

    def extract_email(self, text: str) -> Optional[str]:
        """
        Extrae email del texto.
        
        Args:
            text: Texto donde buscar
        
        Returns:
            Email encontrado o None
        """
        pattern = r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
        match = re.search(pattern, text)
        return match.group(1) if match else None

    def extract_phone(self, text: str) -> Optional[str]:
        """
        Extrae teléfono del texto.
        
        Args:
            text: Texto donde buscar
        
        Returns:
            Teléfono encontrado o None
        """
        # Teléfono mexicano: 10 dígitos
        pattern = r'\b(\d{10})\b'
        match = re.search(pattern, text)
        return match.group(1) if match else None

    def extract_all_data(self, text: str) -> Dict[str, any]:
        """
        Extrae todos los datos posibles del texto.
        
        Args:
            text: Texto donde buscar
        
        Returns:
            Diccionario con todos los datos encontrados
        """
        return {
            "curp": self.extract_curp(text),
            "nss": self.extract_nss(text),
            "rfc": self.extract_rfc(text),
            "email": self.extract_email(text),
            "phone": self.extract_phone(text),
            "dates": self.extract_dates(text),
            "raw_text": text,
        }

    def extract_from_screenshot(self, screenshot_path: str) -> Dict[str, any]:
        """
        Extrae datos de un screenshot de página web.
        
        Args:
            screenshot_path: Ruta al screenshot
        
        Returns:
            Diccionario con datos extraídos
        """
        print(f"  [OCR] Extrayendo texto de {screenshot_path}...")
        text = self.extract_from_image(screenshot_path)
        data = self.extract_all_data(text)

        from src.utils.pii import sanitize_curp, sanitize_nss
        print(f"  [OCR] Texto extra\u00eddo: {len(text)} caracteres")
        if data["curp"]:
            print(f"  [OCR] CURP encontrada: {sanitize_curp(data['curp'])}")
        if data["nss"]:
            print(f"  [OCR] NSS encontrado: {sanitize_nss(data['nss'])}")

        return data
