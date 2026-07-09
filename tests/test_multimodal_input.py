"""Tests unitarios para MultimodalInput — cobertura completa ≥80%."""
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pytest

from src.exceptions import OCRError, VoiceInputError
from src.utils.multimodal_input import MultimodalInput


def _make_mmi():
    """Crea MultimodalInput sin dependencias externas (voz/OCR)."""
    with patch("builtins.print"):
        with patch("src.utils.multimodal_input.WHISPER_AVAILABLE", False):
            with patch("src.utils.multimodal_input.OCR_AVAILABLE", False):
                return MultimodalInput()


def _mmi_init(whisper=False, ocr=False):
    """Crea MMI parcheando disponibilidad + silenciando prints."""
    vp = patch("src.utils.multimodal_input.VoiceInput") if whisper else nullcontext()
    op = patch("src.utils.multimodal_input.OCRExtractor") if ocr else nullcontext()
    with patch("builtins.print"):
        with patch("src.utils.multimodal_input.WHISPER_AVAILABLE", whisper):
            with patch("src.utils.multimodal_input.OCR_AVAILABLE", ocr):
                with vp, op:
                    return MultimodalInput()


# ── _validar_curp ───────────────────────────────────────────────────────────

class TestValidarCurp:
    """MultimodalInput._validar_curp — validación de formato CURP."""

    def _curp_valida(self, curp):
        return _make_mmi()._validar_curp(curp)

    def test_curp_valida(self):
        assert self._curp_valida("GALJ800101HDFXXXX0") is True

    def test_curp_muy_corta(self):
        assert self._curp_valida("GALJ800101") is False

    def test_curp_muy_larga(self):
        assert self._curp_valida("GALJ800101HDFXXXX012") is False

    def test_curp_con_vocales_consecutivas_prohibidas(self):
        # CUARTA letra no puede ser vocal según especificación original,
        # pero el validador actual solo verifica largo + regex general
        assert self._curp_valida("GALA800101HDFXXXX0") is True  # no rechaza vocales

    def test_curp_con_numeros_en_letras(self):
        assert self._curp_valida("GALJ80A101HDFXXXX0") is False

    def test_curp_vacia(self):
        assert self._curp_valida("") is False

    def test_curp_formato_general(self):
        # Formato correcto: AAAA######HAAAAA## (18 chars)
        assert self._curp_valida("AAAA000101HAAAAA00") is True

    def test_curp_con_minusculas(self):
        # _validar_curp no hace .upper() — eso se hace en _get_curp_text
        assert self._curp_valida("galj800101hdfxxxx0") is False

    def test_curp_con_digito_extra(self):
        assert self._curp_valida("GALJ800101HDFXXXX01") is False

    def test_curp_sin_separador(self):
        assert self._curp_valida("GALJ800101HDFXXXX") is False  # 17 chars


# ── __init__ — 4 caminos ────────────────────────────────────────────────────

class TestMultimodalInit:
    def test_init_both_available(self):
        mm = _mmi_init(whisper=True, ocr=True)
        assert mm.voice is not None
        assert mm.ocr is not None

    def test_init_both_unavailable(self):
        mm = _mmi_init(whisper=False, ocr=False)
        assert mm.voice is None
        assert mm.ocr is None

    def test_init_voice_error(self):
        with patch("builtins.print"):
            with patch("src.utils.multimodal_input.WHISPER_AVAILABLE", True):
                with patch("src.utils.multimodal_input.VoiceInput",
                           side_effect=Exception("fail")):
                    mm = MultimodalInput()
        assert mm.voice is None

    def test_init_ocr_error(self):
        with patch("builtins.print"):
            with patch("src.utils.multimodal_input.OCR_AVAILABLE", True):
                with patch("src.utils.multimodal_input.OCRExtractor",
                           side_effect=Exception("fail")):
                    mm = MultimodalInput()
        assert mm.ocr is None


# ── get_curp — dispatch + 3 modos ───────────────────────────────────────────

class TestGetCurp:
    """get_curp — todos los modos de entrada."""

    def test_text(self):
        with patch("builtins.input", return_value="GALJ800101HDFXXXX0"):
            mm = _make_mmi()
            assert mm.get_curp(mode="text") == "GALJ800101HDFXXXX0"

    def test_text_reentry(self):
        """Primera entrada inválida, segunda válida."""
        with patch("builtins.input", side_effect=["invalida", "GALJ800101HDFXXXX0"]):
            mm = _make_mmi()
            assert mm.get_curp(mode="text") == "GALJ800101HDFXXXX0"

    def test_voice(self):
        mm = _make_mmi()
        mm.voice = MagicMock()
        mm.voice.get_curp_interactive.return_value = "GALJ800101HDFXXXX0"
        assert mm.get_curp(mode="voice") == "GALJ800101HDFXXXX0"

    def test_voice_unavailable(self):
        mm = _make_mmi()
        with pytest.raises(VoiceInputError):
            mm.get_curp(mode="voice")

    def test_image_file_ok(self):
        mm = _make_mmi()
        mm.ocr = MagicMock()
        mm.ocr.extract_from_screenshot.return_value = {"curp": "GALJ800101HDFXXXX0"}
        with patch("builtins.input", side_effect=["2", "/fake/path.jpg"]):
            with patch("os.path.exists", return_value=True):
                assert mm.get_curp(mode="image") == "GALJ800101HDFXXXX0"

    def test_image_file_not_found(self):
        mm = _make_mmi()
        mm.ocr = MagicMock()
        with patch("builtins.input", side_effect=["2", "/no/existe.jpg"]):
            with patch("os.path.exists", return_value=False):
                with pytest.raises(FileNotFoundError):
                    mm.get_curp(mode="image")

    def test_image_no_data(self):
        mm = _make_mmi()
        mm.ocr = MagicMock()
        mm.ocr.extract_from_screenshot.return_value = {"curp": None}
        with patch("builtins.input", side_effect=["2", "/fake/path.jpg"]):
            with patch("os.path.exists", return_value=True):
                with pytest.raises(OCRError, match="No se pudo extraer CURP"):
                    mm.get_curp(mode="image")

    def test_image_option_not_2(self):
        """Opción 1 (o cualquier otra que no sea 2) → NotImplementedError."""
        mm = _make_mmi()
        mm.ocr = MagicMock()
        with patch("builtins.input", return_value="1"):
            with pytest.raises(NotImplementedError):
                mm.get_curp(mode="image")

    def test_image_unavailable(self):
        mm = _make_mmi()
        with pytest.raises(OCRError, match="Entrada por imagen no disponible"):
            mm.get_curp(mode="image")

    def test_auto(self):
        with patch.object(MultimodalInput, "_select_mode", return_value="text"):
            with patch("builtins.input", return_value="GALJ800101HDFXXXX0"):
                mm = _make_mmi()
                assert mm.get_curp(mode="auto") == "GALJ800101HDFXXXX0"

    def test_invalid_mode(self):
        mm = _make_mmi()
        with pytest.raises(ValueError, match="Modo inválido"):
            mm.get_curp(mode="invalid")


# ── get_email — dispatch + 3 modos ──────────────────────────────────────────

class TestGetEmail:
    """get_email — todos los modos de entrada."""

    def test_text(self):
        with patch("builtins.input", return_value="user@example.com"):
            mm = _make_mmi()
            assert mm.get_email(mode="text") == "user@example.com"

    def test_text_reentry(self):
        """Primera entrada sin @, segunda válida."""
        with patch("builtins.input", side_effect=["invalido", "user@example.com"]):
            mm = _make_mmi()
            assert mm.get_email(mode="text") == "user@example.com"

    def test_voice(self):
        mm = _make_mmi()
        mm.voice = MagicMock()
        mm.voice.get_email_interactive.return_value = "user@example.com"
        assert mm.get_email(mode="voice") == "user@example.com"

    def test_voice_unavailable(self):
        mm = _make_mmi()
        with pytest.raises(VoiceInputError):
            mm.get_email(mode="voice")

    def test_image_file_ok(self):
        mm = _make_mmi()
        mm.ocr = MagicMock()
        mm.ocr.extract_from_screenshot.return_value = {"email": "user@example.com"}
        with patch("builtins.input", return_value="/fake/path.jpg"):
            with patch("os.path.exists", return_value=True):
                assert mm.get_email(mode="image") == "user@example.com"

    def test_image_file_not_found(self):
        mm = _make_mmi()
        mm.ocr = MagicMock()
        with patch("builtins.input", return_value="/no/existe.jpg"):
            with patch("os.path.exists", return_value=False):
                with pytest.raises(FileNotFoundError):
                    mm.get_email(mode="image")

    def test_image_no_data(self):
        mm = _make_mmi()
        mm.ocr = MagicMock()
        mm.ocr.extract_from_screenshot.return_value = {"email": None}
        with patch("builtins.input", return_value="/fake/path.jpg"):
            with patch("os.path.exists", return_value=True):
                with pytest.raises(OCRError, match="No se pudo extraer email"):
                    mm.get_email(mode="image")

    def test_auto(self):
        with patch.object(MultimodalInput, "_select_mode", return_value="text"):
            with patch("builtins.input", return_value="user@example.com"):
                mm = _make_mmi()
                assert mm.get_email(mode="auto") == "user@example.com"

    def test_invalid_mode(self):
        mm = _make_mmi()
        with pytest.raises(ValueError, match="Modo inválido"):
            mm.get_email(mode="invalid")

    def test_image_unavailable(self):
        mm = _make_mmi()
        with pytest.raises(OCRError):
            mm.get_email(mode="image")


# ── get_placa — dispatch + 3 modos ──────────────────────────────────────────

class TestGetPlaca:
    """get_placa — todos los modos de entrada."""

    def test_text(self):
        with patch("builtins.input", return_value="ABC1234"):
            mm = _make_mmi()
            assert mm.get_placa(mode="text") == "ABC1234"

    def test_text_too_short(self):
        """Menos de 6 chars → rechaza, reintenta."""
        with patch("builtins.input", side_effect=["AB", "ABC1234"]):
            mm = _make_mmi()
            assert mm.get_placa(mode="text") == "ABC1234"

    def test_voice_extracted(self):
        """Voice devuelve placa parseada."""
        mm = _make_mmi()
        mm.voice = MagicMock()
        mm.voice.listen_and_transcribe.return_value = "ABC uno dos tres cuatro"
        mm.voice.extract_placa.return_value = "ABC1234"
        assert mm.get_placa(mode="voice") == "ABC1234"

    def test_voice_fallback(self):
        """extract_placa falla → fallback a texto limpio."""
        mm = _make_mmi()
        mm.voice = MagicMock()
        mm.voice.listen_and_transcribe.return_value = "abc uno dos tres cuatro"
        mm.voice.extract_placa.return_value = None
        assert mm.get_placa(mode="voice") == "ABCUNOD"  # .upper().replace(" ","")[:7]

    def test_voice_unavailable(self):
        mm = _make_mmi()
        with pytest.raises(VoiceInputError):
            mm.get_placa(mode="voice")

    def test_image_match(self):
        mm = _make_mmi()
        mm.ocr = MagicMock()
        mm.ocr.extract_from_image.return_value = "ABC1234 texto adicional"
        with patch("builtins.input", return_value="/fake/path.jpg"):
            with patch("os.path.exists", return_value=True):
                assert mm.get_placa(mode="image") == "ABC1234"

    def test_image_no_match(self):
        mm = _make_mmi()
        mm.ocr = MagicMock()
        mm.ocr.extract_from_image.return_value = "sin placa"
        with patch("builtins.input", return_value="/fake/path.jpg"):
            with patch("os.path.exists", return_value=True):
                with pytest.raises(OCRError, match="No se pudo extraer placa"):
                    mm.get_placa(mode="image")

    def test_image_file_not_found(self):
        mm = _make_mmi()
        mm.ocr = MagicMock()
        with patch("builtins.input", return_value="/no/existe.jpg"):
            with patch("os.path.exists", return_value=False):
                with pytest.raises(FileNotFoundError):
                    mm.get_placa(mode="image")

    def test_image_unavailable(self):
        mm = _make_mmi()
        with pytest.raises(OCRError):
            mm.get_placa(mode="image")

    def test_auto(self):
        with patch.object(MultimodalInput, "_select_mode", return_value="text"):
            with patch("builtins.input", return_value="ABC1234"):
                mm = _make_mmi()
                assert mm.get_placa(mode="auto") == "ABC1234"

    def test_invalid_mode(self):
        mm = _make_mmi()
        with pytest.raises(ValueError, match="Modo inválido"):
            mm.get_placa(mode="invalid")


# ── get_generic — 3 modos ──────────────────────────────────────────────────

class TestGetGeneric:
    """get_generic — entrada genérica multimodal."""

    def test_text_valid(self):
        with patch("builtins.input", return_value="valor"):
            mm = _make_mmi()
            assert mm.get_generic("Campo", mode="text") == "valor"

    def test_text_empty_retry(self):
        with patch("builtins.input", side_effect=["", "ok"]):
            mm = _make_mmi()
            assert mm.get_generic("Campo", mode="text") == "ok"

    def test_text_validator_fail_then_pass(self):
        with patch("builtins.input", side_effect=["bad", "good"]):
            mm = _make_mmi()
            assert mm.get_generic("Campo", mode="text",
                                  validator=lambda x: x == "good") == "good"

    def test_voice_available(self):
        mm = _make_mmi()
        mm.voice = MagicMock()
        mm.voice.listen_and_transcribe.return_value = "spoken"
        assert mm.get_generic("Campo", mode="voice") == "spoken"

    def test_voice_unavailable(self):
        mm = _make_mmi()
        with pytest.raises(VoiceInputError):
            mm.get_generic("Campo", mode="voice")

    def test_image_not_implemented(self):
        mm = _make_mmi()
        mm.ocr = MagicMock()
        with pytest.raises(NotImplementedError):
            mm.get_generic("Campo", mode="image")

    def test_image_unavailable(self):
        mm = _make_mmi()
        with pytest.raises(OCRError):
            mm.get_generic("Campo", mode="image")

    def test_auto(self):
        with patch.object(MultimodalInput, "_select_mode", return_value="text"):
            with patch("builtins.input", return_value="auto"):
                mm = _make_mmi()
                assert mm.get_generic("Campo", mode="auto") == "auto"

    def test_invalid_mode(self):
        mm = _make_mmi()
        with pytest.raises(ValueError, match="Modo inválido"):
            mm.get_generic("Campo", mode="invalid")


# ── _select_mode — selector interactivo ────────────────────────────────────

class TestSelectMode:
    """_select_mode — selección interactiva de modo."""

    def test_option_text(self):
        mm = _make_mmi()
        with patch("builtins.input", return_value="1"):
            assert mm._select_mode() == "text"

    def test_option_voice(self):
        mm = _make_mmi()
        mm.voice = MagicMock()
        with patch("builtins.input", return_value="2"):
            assert mm._select_mode() == "voice"

    def test_option_image(self):
        mm = _make_mmi()
        mm.ocr = MagicMock()
        with patch("builtins.input", return_value="3"):
            assert mm._select_mode() == "image"

    def test_option_invalid(self):
        mm = _make_mmi()
        with patch("builtins.input", return_value="999"):
            assert mm._select_mode() == "text"

    def test_option_voice_unavailable_fallback(self):
        """Opción 2 sin voz disponible → fallback a texto."""
        mm = _make_mmi()
        with patch("builtins.input", return_value="2"):
            assert mm._select_mode() == "text"

    def test_option_image_unavailable_fallback(self):
        """Opción 3 sin OCR disponible → fallback a texto."""
        mm = _make_mmi()
        with patch("builtins.input", return_value="3"):
            assert mm._select_mode() == "text"
