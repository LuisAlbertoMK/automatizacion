"""Tests unitarios para utils/ocr.py con pytesseract mockeado."""

import os
import sys
from unittest.mock import patch

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.ocr import OCRError, OCRExtractor  # noqa: E402


@pytest.fixture
def ocr():
    with patch.object(OCRExtractor, "_verify_tesseract"):
        yield OCRExtractor()


# Imagen real minima de 1x1 px para mockear Image.open
_TINY_IMG = Image.new("RGB", (1, 1))


class TestOCRExtractor:
    def test_init(self, ocr):
        assert isinstance(ocr, OCRExtractor)

    @patch("utils.ocr.pytesseract.image_to_string")
    @patch("utils.ocr.Image.open", return_value=_TINY_IMG)
    def test_extract_from_image_basic(self, mock_open, mock_its, ocr):
        mock_its.return_value = "Texto extraido"
        result = ocr.extract_from_image("fake/path.png")
        assert result == "Texto extraido"

    @patch("utils.ocr.pytesseract.image_to_string")
    @patch("utils.ocr.Image.open", return_value=_TINY_IMG)
    def test_extract_from_image_strips_whitespace(self, mock_open, mock_its, ocr):
        mock_its.return_value = "  Hola mundo  \n"
        result = ocr.extract_from_image("fake/path.png")
        assert result == "Hola mundo"

    @patch("utils.ocr.pytesseract.image_to_string")
    @patch("utils.ocr.Image.open", return_value=_TINY_IMG)
    def test_extract_from_image_supports_lang(self, mock_open, mock_its, ocr):
        mock_its.return_value = "Hello world"
        result = ocr.extract_from_image("fake/path.png", lang="eng")
        assert result == "Hello world"
        # Verificar que lang se pasa a pytesseract
        _, kwargs = mock_its.call_args
        assert kwargs.get("lang") == "eng"

    @patch("utils.ocr.Image.open")
    def test_extract_from_image_raises_on_error(self, mock_open, ocr):
        mock_open.side_effect = FileNotFoundError("No such file")
        with pytest.raises(OCRError):
            ocr.extract_from_image("fake/path.png")

    @patch("utils.ocr.pytesseract.image_to_string")
    @patch("utils.ocr.Image.open", return_value=_TINY_IMG)
    def test_extract_from_bytes(self, mock_open, mock_its, ocr):
        mock_its.return_value = "Texto desde bytes"
        result = ocr.extract_from_bytes(b"fake-image-bytes")
        assert result == "Texto desde bytes"

    @patch("utils.ocr.Image.open")
    def test_extract_from_bytes_raises_on_error(self, mock_open, ocr):
        mock_open.side_effect = Exception("Corrupt image")
        with pytest.raises(OCRError):
            ocr.extract_from_bytes(b"corrupt-bytes")
