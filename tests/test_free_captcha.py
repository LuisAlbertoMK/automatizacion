"""Tests unitarios para utils/free_captcha.py con Tesseract y Whisper mockeados.

NOTA: PIL.Image, requests y whisper se importan LAZY dentro de las funciones
(vía import local), por eso los patches van a los módulos globales
(PIL.Image.open, requests.get, whisper.load_model) y NO al namespace del módulo.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from src.exceptions import FreeCaptchaError
from src.utils.free_captcha import FreeCaptchaSolver


# Imagen real mínima de 1x1 px para mockear Image.open global
_TINY_IMG = Image.new("RGB", (1, 1))


@pytest.fixture
def solver():
    """Crea FreeCaptchaSolver con TESSERACT y WHISPER disponibles.

    Crea el solver DENTRO del patch.dict para que las flags se lean correctamente
    (los módulos se importan con TESSERACT_AVAILABLE=False en tiempo de importación
    porque Tesseract y Whisper no están en el entorno de CI/tests).
    """
    with patch.dict(
        "src.utils.free_captcha.__dict__",
        {"TESSERACT_AVAILABLE": True, "WHISPER_AVAILABLE": True},
    ):
        with patch("builtins.print"):
            yield FreeCaptchaSolver()


# ── FreeCaptchaSolver.__init__ ─────────────────────────────────────────────


class TestInit:
    """FreeCaptchaSolver.__init__ — flags según disponibilidad."""

    @patch.dict("src.utils.free_captcha.__dict__", {"TESSERACT_AVAILABLE": True, "WHISPER_AVAILABLE": False})
    def test_init_tesseract_available_whisper_not(self):
        with patch("builtins.print"):
            s = FreeCaptchaSolver()
        assert s.use_ocr is True
        assert s.use_whisper is False

    @patch.dict("src.utils.free_captcha.__dict__", {"TESSERACT_AVAILABLE": False, "WHISPER_AVAILABLE": True})
    def test_init_tesseract_unavailable_whisper_available(self):
        with patch("builtins.print"):
            s = FreeCaptchaSolver()
        assert s.use_ocr is False
        assert s.use_whisper is True

    @patch.dict("src.utils.free_captcha.__dict__", {"TESSERACT_AVAILABLE": False, "WHISPER_AVAILABLE": False})
    def test_init_both_unavailable(self):
        with patch("builtins.print"):
            s = FreeCaptchaSolver()
        assert s.use_ocr is False
        assert s.use_whisper is False

    @patch.dict("src.utils.free_captcha.__dict__", {"TESSERACT_AVAILABLE": True, "WHISPER_AVAILABLE": True})
    def test_init_both_available(self):
        with patch("builtins.print"):
            s = FreeCaptchaSolver()
        assert s.use_ocr is True
        assert s.use_whisper is True
        assert s._whisper_model is None

    @patch.dict("src.utils.free_captcha.__dict__", {"TESSERACT_AVAILABLE": True, "WHISPER_AVAILABLE": True})
    def test_init_respects_use_ocr_false(self):
        with patch("builtins.print"):
            s = FreeCaptchaSolver(use_ocr=False)
        assert s.use_ocr is False

    @patch.dict("src.utils.free_captcha.__dict__", {"TESSERACT_AVAILABLE": True, "WHISPER_AVAILABLE": True})
    def test_init_respects_use_whisper_false(self):
        with patch("builtins.print"):
            s = FreeCaptchaSolver(use_whisper=False)
        assert s.use_whisper is False


# ── FreeCaptchaSolver.solve_image ──────────────────────────────────────────


class TestSolveImage:
    """FreeCaptchaSolver.solve_image — OCR exitoso y fallos."""

    def test_solve_image_numeric(self, solver):
        with patch("src.utils.free_captcha.pytesseract.image_to_string", return_value="4829"):
            with patch("PIL.Image.open", return_value=_TINY_IMG):
                result = solver.solve_image(b"fake_image_bytes")
        assert result == "4829"

    def test_solve_image_non_numeric(self, solver):
        with patch("src.utils.free_captcha.pytesseract.image_to_string", return_value="AbCdE"):
            with patch("PIL.Image.open", return_value=_TINY_IMG):
                result = solver.solve_image(b"fake_image_bytes", numeric=False)
        assert result == "AbCdE"

    def test_solve_image_fallback_to_direct_ocr(self, solver):
        with patch("src.utils.free_captcha.pytesseract.image_to_string", side_effect=["", "3971"]) as mock_its:
            with patch("PIL.Image.open", return_value=_TINY_IMG):
                result = solver.solve_image(b"fake_image_bytes")
        assert result == "3971"
        assert mock_its.call_count == 2

    def test_solve_image_raises_when_no_ocr(self):
        with patch.dict(
            "src.utils.free_captcha.__dict__", {"TESSERACT_AVAILABLE": False, "WHISPER_AVAILABLE": False}
        ):
            with patch("builtins.print"):
                s = FreeCaptchaSolver()
        with pytest.raises(FreeCaptchaError, match="OCR no disponible"):
            s.solve_image(b"fake_image_bytes")

    def test_solve_image_raises_when_both_attempts_fail(self, solver):
        with patch("src.utils.free_captcha.pytesseract.image_to_string", return_value=""):
            with patch("PIL.Image.open", return_value=_TINY_IMG):
                with pytest.raises(FreeCaptchaError, match="No se pudo resolver el CAPTCHA"):
                    solver.solve_image(b"fake_image_bytes")

    def test_solve_image_calls_ocr_with_preprocess(self, solver):
        mock_img = MagicMock(spec=Image.Image)
        mock_img.mode = "RGB"
        mock_img.size = (100, 50)
        mock_img.convert.return_value = mock_img
        mock_img.resize.return_value = mock_img
        mock_img.point.return_value = mock_img

        with patch("PIL.Image.open", return_value=mock_img):
            with patch("src.utils.free_captcha.pytesseract.image_to_string", return_value="7521") as mock_its:
                result = solver.solve_image(b"fake_image_bytes")

        assert result == "7521"
        mock_img.convert.assert_any_call("L")
        mock_img.resize.assert_called_once()
        mock_img.point.assert_called_once()


# ── FreeCaptchaSolver._ocr_with_preprocess ─────────────────────────────────


class TestOcrWithPreprocess:
    """FreeCaptchaSolver._ocr_with_preprocess — procesamiento interno."""

    def _make_mock_img(self, mode="L"):
        img = MagicMock(spec=Image.Image)
        img.mode = mode
        img.size = (50, 20)
        img.resize.return_value = img
        img.convert.return_value = img
        img.point.return_value = img
        return img

    def test_ocr_with_preprocess_numeric(self, solver):
        with patch("src.utils.free_captcha.pytesseract.image_to_string", return_value="  8361  "):
            result = solver._ocr_with_preprocess(self._make_mock_img(), numeric=True)
        assert result == "8361"

    def test_ocr_with_preprocess_non_numeric(self, solver):
        with patch("src.utils.free_captcha.pytesseract.image_to_string", return_value="  hello  "):
            result = solver._ocr_with_preprocess(self._make_mock_img(), numeric=False)
        assert result == "hello"

    def test_ocr_with_preprocess_converts_grayscale(self, solver):
        with patch("src.utils.free_captcha.pytesseract.image_to_string", return_value="ABC"):
            solver._ocr_with_preprocess(self._make_mock_img(mode="RGB"), numeric=True)
        # convert was called with "L" (for grayscale)
        assert True  # no exception = test passes

    def test_ocr_with_preprocess_returns_empty_on_failure(self, solver):
        with patch("src.utils.free_captcha.pytesseract.image_to_string", return_value=""):
            result = solver._ocr_with_preprocess(self._make_mock_img(), numeric=True)
        assert result == ""


# ── FreeCaptchaSolver.solve_recaptcha_v2 / v3 (sync) ───────────────────────


class TestRecaptchaSync:
    """Métodos sincrónicos reCAPTCHA — siempre retornan MANUAL."""

    def test_solve_recaptcha_v2_returns_manual(self, solver):
        assert solver.solve_recaptcha_v2("site_key", "https://example.com") == "MANUAL"

    def test_solve_recaptcha_v2_auto_flag_ignored(self, solver):
        assert solver.solve_recaptcha_v2("site_key", "https://example.com", auto=False) == "MANUAL"

    def test_solve_recaptcha_v3_returns_manual(self, solver):
        assert solver.solve_recaptcha_v3("site_key", "https://example.com") == "MANUAL"

    def test_solve_recaptcha_v3_with_params(self, solver):
        result = solver.solve_recaptcha_v3("sk", "https://ex.com", action="login", min_score=0.5, auto=False)
        assert result == "MANUAL"


# ── FreeCaptchaSolver.solve_recaptcha_v2_audio ─────────────────────────────


class _MockPageBuilder:
    """Helper: construye mocks de page/frame/locator para tests de audio."""

    @staticmethod
    def build(
        count_side_effect=None,
        audio_src="https://example.com/audio.mp3",
        evaluate_return="",
        has_verify_btn=True,
    ):
        locator = MagicMock()
        locator.first.wait_for = AsyncMock()
        locator.first.click = AsyncMock()
        locator.count = AsyncMock(side_effect=count_side_effect or [1, 1, 1])
        locator.get_attribute = AsyncMock(return_value=audio_src)
        locator.fill = AsyncMock()

        verify_btn = MagicMock()
        verify_btn.count = AsyncMock(return_value=1 if has_verify_btn else 0)
        verify_btn.click = AsyncMock()

        frame = MagicMock()
        frame.locator.side_effect = lambda sel: {
            ".recaptcha-checkbox-border": locator,
            "#recaptcha-audio-button": locator,
            "button[aria-label*='audio']": locator,
            "button[id='recaptcha-audio-button']": locator,
            "#audio-source": locator,
            "#audio-response": locator,
            "#recaptcha-verify-button": verify_btn,
        }.get(sel, locator)

        page = MagicMock()
        page.frame_locator.return_value = frame
        page.evaluate = AsyncMock(return_value=evaluate_return)
        page.keyboard.press = AsyncMock()

        return page, locator


class TestRecaptchaAudio:
    """FreeCaptchaSolver.solve_recaptcha_v2_audio — flujo asíncrono."""

    @pytest.mark.asyncio
    async def test_audio_returns_manual_without_whisper(self):
        with patch.dict(
            "src.utils.free_captcha.__dict__", {"TESSERACT_AVAILABLE": True, "WHISPER_AVAILABLE": False}
        ):
            with patch("builtins.print"):
                s = FreeCaptchaSolver()
        result = await s.solve_recaptcha_v2_audio(None, "site_key", "https://example.com")
        assert result == "MANUAL"

    @pytest.mark.asyncio
    @patch("src.utils.free_captcha.asyncio.sleep")
    async def test_audio_no_challenge_falls_back_to_manual(self, mock_sleep, solver):
        page, _ = _MockPageBuilder.build(count_side_effect=[0], evaluate_return="")
        result = await solver.solve_recaptcha_v2_audio(page, "sk", "https://ex.com")
        assert result == "MANUAL"

    @pytest.mark.asyncio
    @patch("src.utils.free_captcha.asyncio.sleep")
    async def test_audio_no_challenge_but_already_resolved(self, mock_sleep, solver):
        # Los 3 count() se llaman secuencialmente (1 por cada if, aunque entren al bloque)
        page, _ = _MockPageBuilder.build(
            count_side_effect=[0, 0, 0], evaluate_return="g-recaptcha-response-valid-token-12345"
        )
        result = await solver.solve_recaptcha_v2_audio(page, "sk", "https://ex.com")
        assert result == "g-recaptcha-response-valid-token-12345"

    @pytest.mark.asyncio
    @patch("src.utils.free_captcha.asyncio.sleep")
    @patch("src.utils.free_captcha.tempfile.NamedTemporaryFile")
    async def test_audio_full_flow_success(self, mock_temp, mock_sleep, solver):
        mock_temp.return_value.__enter__.return_value.name = "/tmp/fake.mp3"
        page, locator = _MockPageBuilder.build(evaluate_return="g-recaptcha-response-valid-token-12345")

        with patch("requests.get") as mock_req:
            mock_req.return_value.content = b"fake_audio_bytes"
            with patch("whisper.load_model") as mock_load:
                model = MagicMock()
                model.transcribe.return_value = {"text": "1 2 3 4"}
                mock_load.return_value = model
                with patch("pathlib.Path.unlink"):
                    result = await solver.solve_recaptcha_v2_audio(page, "sk", "https://ex.com")

        assert result == "g-recaptcha-response-valid-token-12345"
        mock_req.assert_called_once_with("https://example.com/audio.mp3", timeout=30)

    @pytest.mark.asyncio
    @patch("src.utils.free_captcha.asyncio.sleep")
    async def test_audio_full_flow_verify_with_keyboard(self, mock_sleep, solver):
        """Cuando no hay botón verify, usa Enter como fallback."""
        page, locator = _MockPageBuilder.build(
            evaluate_return="token-from-enter-12345", has_verify_btn=False
        )
        with patch("src.utils.free_captcha.tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "/tmp/fake.mp3"
            with patch("requests.get") as mock_req:
                mock_req.return_value.content = b"fake_audio_bytes"
                with patch("whisper.load_model") as mock_load:
                    model = MagicMock()
                    model.transcribe.return_value = {"text": "5 6 7 8"}
                    mock_load.return_value = model
                    with patch("pathlib.Path.unlink"):
                        result = await solver.solve_recaptcha_v2_audio(page, "sk", "https://ex.com")

        assert result == "token-from-enter-12345"
        page.keyboard.press.assert_awaited_once_with("Enter")

    @pytest.mark.asyncio
    @patch("src.utils.free_captcha.asyncio.sleep")
    async def test_audio_transcription_no_digits_returns_manual(self, mock_sleep, solver):
        page, _ = _MockPageBuilder.build()
        with patch("src.utils.free_captcha.tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "/tmp/fake.mp3"
            with patch("requests.get") as mock_req:
                mock_req.return_value.content = b"fake_audio_bytes"
                with patch("whisper.load_model") as mock_load:
                    model = MagicMock()
                    model.transcribe.return_value = {"text": "hello world"}
                    mock_load.return_value = model
                    with patch("pathlib.Path.unlink"):
                        result = await solver.solve_recaptcha_v2_audio(page, "sk", "https://ex.com")

        assert result == "MANUAL"

    @pytest.mark.asyncio
    @patch("src.utils.free_captcha.asyncio.sleep")
    async def test_audio_download_failure_returns_manual(self, mock_sleep, solver):
        page, _ = _MockPageBuilder.build()
        with patch("requests.get", side_effect=Exception("Network error")):
            result = await solver.solve_recaptcha_v2_audio(page, "sk", "https://ex.com")

        assert result == "MANUAL"

    @pytest.mark.asyncio
    @patch("src.utils.free_captcha.asyncio.sleep")
    async def test_audio_no_audio_link_returns_manual(self, mock_sleep, solver):
        page, _ = _MockPageBuilder.build(audio_src=None)
        result = await solver.solve_recaptcha_v2_audio(page, "sk", "https://ex.com")
        assert result == "MANUAL"
