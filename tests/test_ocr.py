"""Tests unitarios para utils/ocr.py con pytesseract mockeado."""

import os
import sys
from unittest.mock import patch

import pytest
from PIL import Image

from src.utils.ocr import OCRError, OCRExtractor  # noqa: E402


@pytest.fixture
def ocr():
    with patch.object(OCRExtractor, "_verify_tesseract"):
        yield OCRExtractor()


# Imagen real minima de 1x1 px para mockear Image.open
_TINY_IMG = Image.new("RGB", (1, 1))


class TestVerifyTesseract:
    """Lines 44-51: _verify_tesseract success y exception paths."""

    @patch("src.utils.ocr.pytesseract.get_tesseract_version")
    def test_verify_tesseract_ok(self, mock_version):
        extractor = OCRExtractor()
        # Parchear después de init (que llama _verify_tesseract automáticamente)
        # En realidad el mock ya se aplicó en __init__
        assert extractor is not None
        mock_version.assert_called_once()

    def test_verify_tesseract_fail(self):
        """Sin mock, get_tesseract_version falla (Tesseract no instalado en CI)."""
        with patch("src.utils.ocr.pytesseract.get_tesseract_version", side_effect=Exception("No Tesseract")):
            extractor = OCRExtractor()
            assert extractor is not None


class TestExtractFromPdf:
    """Lines 103-123: extract_from_pdf con 3 ramas."""

    @patch("src.utils.ocr.pytesseract.image_to_string", return_value="texto pdf")
    @patch("pdf2image.convert_from_path")
    def test_extract_from_pdf_basic(self, mock_convert, mock_its, ocr):
        mock_convert.return_value = [_TINY_IMG, _TINY_IMG]
        result = ocr.extract_from_pdf("fake/doc.pdf")
        assert result == "texto pdf\n\ntexto pdf"
        assert mock_convert.call_count == 1

    @patch("src.utils.ocr.pytesseract.image_to_string", return_value="")
    @patch("pdf2image.convert_from_path")
    def test_extract_from_pdf_single_page(self, mock_convert, mock_its, ocr):
        mock_convert.return_value = [_TINY_IMG]
        result = ocr.extract_from_pdf("fake/single.pdf")
        assert result == ""

    @patch("src.utils.ocr.pytesseract.image_to_string", return_value="x")
    @patch("pdf2image.convert_from_path")
    def test_extract_from_pdf_import_error(self, mock_convert, mock_its, ocr):
        """ImportError cuando pdf2image no está instalado."""
        mock_convert.side_effect = ImportError("No module pdf2image")
        with pytest.raises(OCRError, match="pdf2image"):
            ocr.extract_from_pdf("fake/doc.pdf")

    @patch("src.utils.ocr.pytesseract.image_to_string", return_value="x")
    @patch("pdf2image.convert_from_path")
    def test_extract_from_pdf_generic_error(self, mock_convert, mock_its, ocr):
        """Exception genérica en extract_from_pdf."""
        mock_convert.side_effect = Exception("PDF corrupto")
        with pytest.raises(OCRError, match="Error extrayendo texto de PDF"):
            ocr.extract_from_pdf("fake/corrupt.pdf")


class TestDataExtractors:
    """Lines 158-274: extractores específicos de datos."""

    # extract_curp (169-171)
    def test_extract_curp_found(self, ocr):
        result = ocr.extract_curp("Mi CURP es GOGG800101HDFPLN08")
        assert result == "GOGG800101HDFPLN08"

    def test_extract_curp_not_found(self, ocr):
        assert ocr.extract_curp("No hay curp aquí") is None

    def test_extract_curp_case_insensitive(self, ocr):
        result = ocr.extract_curp("curp: gogg800101hdfpln08")
        assert result == "GOGG800101HDFPLN08"

    # extract_nss (184-186)
    def test_extract_nss_found(self, ocr):
        result = ocr.extract_nss("NSS: 12345678901")
        assert result == "12345678901"

    def test_extract_nss_not_found(self, ocr):
        assert ocr.extract_nss("sin numero") is None

    # extract_rfc (199-201)
    def test_extract_rfc_found(self, ocr):
        result = ocr.extract_rfc("RFC: GOGG800101XXX")
        assert result == "GOGG800101XXX"

    def test_extract_rfc_not_found(self, ocr):
        assert ocr.extract_rfc("sin rfc") is None

    # extract_dates (213-225)
    def test_extract_dates_multiple(self, ocr):
        result = ocr.extract_dates("Fechas: 01/01/2024 y 2024-12-31")
        assert "01/01/2024" in result
        assert "2024-12-31" in result

    def test_extract_dates_empty(self, ocr):
        assert ocr.extract_dates("sin fechas") == []

    # extract_email (237-239)
    def test_extract_email_found(self, ocr):
        result = ocr.extract_email("Email: test@example.com")
        assert result == "test@example.com"

    def test_extract_email_not_found(self, ocr):
        assert ocr.extract_email("sin email") is None

    # extract_phone (252-254)
    def test_extract_phone_found(self, ocr):
        result = ocr.extract_phone("Tel: 5512345678")
        assert result == "5512345678"

    def test_extract_phone_not_found(self, ocr):
        assert ocr.extract_phone("sin telefono") is None

    # extract_all_data (266)
    def test_extract_all_data(self, ocr):
        text = "CURP GOGG800101HDFPLN08 NSS 12345678901 test@mail.com 5512345678"
        data = ocr.extract_all_data(text)
        assert data["curp"] == "GOGG800101HDFPLN08"
        assert data["nss"] == "12345678901"
        assert data["email"] == "test@mail.com"
        assert data["phone"] == "5512345678"
        assert data["raw_text"] == text


class TestExtractFromScreenshot:
    """Lines 286-296: extract_from_screenshot integra image + all_data."""

    @patch("src.utils.ocr.pytesseract.image_to_string", return_value="CURP GOGG800101HDFPLN08")
    @patch("src.utils.ocr.Image.open", return_value=_TINY_IMG)
    def test_screenshot_with_curp(self, mock_open, mock_its, ocr):
        result = ocr.extract_from_screenshot("fake/screen.png")
        assert result["curp"] == "GOGG800101HDFPLN08"
        assert "raw_text" in result

    @patch("src.utils.ocr.pytesseract.image_to_string", return_value="sin datos importantes")
    @patch("src.utils.ocr.Image.open", return_value=_TINY_IMG)
    def test_screenshot_no_data(self, mock_open, mock_its, ocr):
        result = ocr.extract_from_screenshot("fake/screen.png")
        assert result["curp"] is None
        assert result["nss"] is None

    @patch("src.utils.ocr.pytesseract.image_to_string", return_value="CURP GOGG800101HDFPLN08 NSS 12345678901")
    @patch("src.utils.ocr.Image.open", return_value=_TINY_IMG)
    def test_screenshot_with_nss(self, mock_open, mock_its, ocr):
        """Line 294: NSS encontrado en screenshot."""
        result = ocr.extract_from_screenshot("fake/screen.png")
        assert result["nss"] == "12345678901"
        assert result["curp"] == "GOGG800101HDFPLN08"


class TestOCRExtractor:
    def test_init(self, ocr):
        assert isinstance(ocr, OCRExtractor)

    @patch("src.utils.ocr.pytesseract.image_to_string")
    @patch("src.utils.ocr.Image.open", return_value=_TINY_IMG)
    def test_extract_from_image_basic(self, mock_open, mock_its, ocr):
        mock_its.return_value = "Texto extraido"
        result = ocr.extract_from_image("fake/path.png")
        assert result == "Texto extraido"

    @patch("src.utils.ocr.pytesseract.image_to_string")
    @patch("src.utils.ocr.Image.open", return_value=_TINY_IMG)
    def test_extract_from_image_strips_whitespace(self, mock_open, mock_its, ocr):
        mock_its.return_value = "  Hola mundo  \n"
        result = ocr.extract_from_image("fake/path.png")
        assert result == "Hola mundo"

    @patch("src.utils.ocr.pytesseract.image_to_string")
    @patch("src.utils.ocr.Image.open", return_value=_TINY_IMG)
    def test_extract_from_image_supports_lang(self, mock_open, mock_its, ocr):
        mock_its.return_value = "Hello world"
        result = ocr.extract_from_image("fake/path.png", lang="eng")
        assert result == "Hello world"
        # Verificar que lang se pasa a pytesseract
        _, kwargs = mock_its.call_args
        assert kwargs.get("lang") == "eng"

    @patch("src.utils.ocr.Image.open")
    def test_extract_from_image_raises_on_error(self, mock_open, ocr):
        mock_open.side_effect = FileNotFoundError("No such file")
        with pytest.raises(OCRError):
            ocr.extract_from_image("fake/path.png")

    @patch("src.utils.ocr.pytesseract.image_to_string")
    @patch("src.utils.ocr.Image.open", return_value=_TINY_IMG)
    def test_extract_from_bytes(self, mock_open, mock_its, ocr):
        mock_its.return_value = "Texto desde bytes"
        result = ocr.extract_from_bytes(b"fake-image-bytes")
        assert result == "Texto desde bytes"

    @patch("src.utils.ocr.Image.open")
    def test_extract_from_bytes_raises_on_error(self, mock_open, ocr):
        mock_open.side_effect = Exception("Corrupt image")
        with pytest.raises(OCRError):
            ocr.extract_from_bytes(b"corrupt-bytes")
