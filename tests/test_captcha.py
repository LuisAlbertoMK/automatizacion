"""Tests unitarios para utils/captcha.py con 2captcha mockeado."""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests

os.environ["CAPTCHA_API_KEY"] = "test_api_key_12345"

from src.utils.captcha import CaptchaError, CaptchaSolver  # noqa: E402


@pytest.fixture
def solver():
    with patch.object(CaptchaSolver, "_verify_balance"):
        yield CaptchaSolver()


class TestVerifyBalance:
    """Lines 35-50: _verify_balance en todas sus ramas."""

    @patch("src.utils.captcha.requests.get")
    def test_balance_ok(self, mock_get):
        """Saldo suficiente no debe fallar."""
        mock_get.return_value.text = "5.5000"
        solver = CaptchaSolver()
        assert solver is not None

    @patch("src.utils.captcha.requests.get")
    def test_balance_insufficient(self, mock_get):
        """Balance < 0.001 debe levantar CaptchaError."""
        mock_get.return_value.text = "0.0005"
        with pytest.raises(CaptchaError, match="Saldo insuficiente"):
            CaptchaSolver()

    @patch("src.utils.captcha.requests.get")
    def test_balance_request_error_caught(self, mock_get):
        """RequestException no bloquea."""
        mock_get.side_effect = requests.RequestException("Timeout")
        solver = CaptchaSolver()
        assert solver is not None

    @patch("src.utils.captcha.requests.get")
    def test_balance_value_error_caught(self, mock_get):
        """ValueError en balance no bloquea."""
        mock_get.return_value.text = "not-a-number"
        solver = CaptchaSolver()
        assert solver is not None


class TestRecaptchaErrors:
    """Lines 115, 161: error paths en métodos sync."""

    @patch("src.utils.captcha.requests.post")
    def test_recaptcha_v2_error(self, mock_post, solver):
        mock_post.return_value.json.return_value = {"status": 0, "request": "ERROR"}
        with pytest.raises(CaptchaError, match="Error enviando reCAPTCHA v2"):
            solver.solve_recaptcha_v2("site_key", "https://test.com")

    def test_recaptcha_v3_manual(self, solver):
        """Line 143-145: v3 con auto=False."""
        assert solver.solve_recaptcha_v3("site_key", "https://test.com", auto=False) == "MANUAL"

    @patch("src.utils.captcha.requests.post")
    def test_recaptcha_v3_error(self, mock_post, solver):
        mock_post.return_value.json.return_value = {"status": 0, "request": "ERROR"}
        with pytest.raises(CaptchaError, match="Error enviando reCAPTCHA v3"):
            solver.solve_recaptcha_v3("site_key", "https://test.com")

    @patch("src.utils.captcha.requests.post")
    def test_recaptcha_v3_success(self, mock_post, solver):
        mock_post.return_value.json.return_value = {"status": 1, "request": "task123"}
        solver._wait_for_result = Mock(return_value="v3-token")
        assert solver.solve_recaptcha_v3("site_key", "https://test.com") == "v3-token"


class TestAsyncMethods:
    """Lines 170-259: métodos async completos."""

    @patch("src.utils.captcha.requests.post")
    async def test_solve_image_async_success(self, mock_post, solver):
        """Line 172-183: solve_image_async."""
        mock_post.return_value.json.return_value = {"status": 1, "request": "task123"}
        solver._wait_for_result_async = AsyncMock(return_value="async-solution")
        result = await solver.solve_image_async(b"fake-image-bytes")
        assert result == "async-solution"

    @patch("src.utils.captcha.requests.post")
    async def test_solve_image_async_error(self, mock_post, solver):
        mock_post.return_value.json.return_value = {"status": 0, "request": "ERROR"}
        with pytest.raises(CaptchaError, match="Error enviando imagen"):
            await solver.solve_image_async(b"fake-image-bytes")

    @patch("src.utils.captcha.requests.post")
    async def test_solve_recaptcha_v2_async_success(self, mock_post, solver):
        """Line 187-199: solve_recaptcha_v2_async."""
        mock_post.return_value.json.return_value = {"status": 1, "request": "task123"}
        solver._wait_for_result_async = AsyncMock(return_value="async-v2-token")
        result = await solver.solve_recaptcha_v2_async("site_key", "https://test.com")
        assert result == "async-v2-token"

    async def test_solve_recaptcha_v2_async_manual(self, solver):
        assert await solver.solve_recaptcha_v2_async("site_key", "https://test.com", auto=False) == "MANUAL"

    @patch("src.utils.captcha.requests.post")
    async def test_solve_recaptcha_v2_async_error(self, mock_post, solver):
        """Line 197: error en v2 async."""
        mock_post.return_value.json.return_value = {"status": 0, "request": "ERROR_V2"}
        with pytest.raises(CaptchaError, match="Error enviando reCAPTCHA v2"):
            await solver.solve_recaptcha_v2_async("site_key", "https://test.com")

    @patch("src.utils.captcha.requests.post")
    async def test_solve_recaptcha_v3_async_success(self, mock_post, solver):
        """Line 206-219: solve_recaptcha_v3_async."""
        mock_post.return_value.json.return_value = {"status": 1, "request": "task123"}
        solver._wait_for_result_async = AsyncMock(return_value="async-v3-token")
        result = await solver.solve_recaptcha_v3_async("site_key", "https://test.com")
        assert result == "async-v3-token"

    async def test_solve_recaptcha_v3_async_manual(self, solver):
        assert await solver.solve_recaptcha_v3_async("site_key", "https://test.com", auto=False) == "MANUAL"

    @patch("src.utils.captcha.requests.post")
    async def test_solve_recaptcha_v3_async_error(self, mock_post, solver):
        """Line 217: error en v3 async."""
        mock_post.return_value.json.return_value = {"status": 0, "request": "ERROR_V3"}
        with pytest.raises(CaptchaError, match="Error enviando reCAPTCHA v3"):
            await solver.solve_recaptcha_v3_async("site_key", "https://test.com")

    @patch("src.utils.captcha.requests.get")
    async def test_wait_for_result_async_success(self, mock_get, solver):
        """Line 227-259: _wait_for_result_async polling exitoso."""
        mock_get.return_value.json.side_effect = [
            {"status": 0, "request": "CAPTCHA_NOT_READY"},
            {"status": 1, "request": "async-solution"},
        ]
        with patch("src.utils.captcha.asyncio.sleep"):
            result = await solver._wait_for_result_async("task_id", max_wait=20)
        assert result == "async-solution"
        assert mock_get.call_count == 2

    @patch("src.utils.captcha.requests.get")
    async def test_wait_for_result_async_timeout(self, mock_get, solver):
        mock_get.return_value.json.return_value = {"status": 0, "request": "CAPTCHA_NOT_READY"}
        with patch("src.utils.captcha.asyncio.sleep"):
            with pytest.raises(CaptchaError, match="Timeout"):
                await solver._wait_for_result_async("task_id", max_wait=6)

    @patch("src.utils.captcha.requests.get")
    async def test_wait_for_result_async_api_error(self, mock_get, solver):
        mock_get.return_value.json.return_value = {"status": 0, "request": "ERROR_NO_SLOT"}
        with patch("src.utils.captcha.asyncio.sleep"):
            with pytest.raises(CaptchaError, match="ERROR_NO_SLOT"):
                await solver._wait_for_result_async("task_id", max_wait=20)

    @patch("src.utils.captcha.requests.get")
    async def test_wait_for_result_async_retry_network(self, mock_get, solver):
        """Retry en error de red (exponential backoff)."""
        ok_response = Mock()
        ok_response.json.return_value = {"status": 1, "request": "solution"}
        mock_get.side_effect = [requests.exceptions.ConnectionError("Network down"), ok_response]
        with patch("src.utils.captcha.asyncio.sleep"):
            result = await solver._wait_for_result_async("task_id", max_wait=30)
        assert result == "solution"
        assert mock_get.call_count == 2

    @patch("src.utils.captcha.requests.get")
    async def test_wait_for_result_async_max_retries(self, mock_get, solver):
        mock_get.side_effect = requests.exceptions.ConnectionError("Network down")
        with patch("src.utils.captcha.asyncio.sleep"):
            with pytest.raises(CaptchaError, match="reintentos"):
                await solver._wait_for_result_async("task_id", max_wait=120)

    @patch("src.utils.captcha.requests.get")
    async def test_wait_for_result_async_not_ready_typo(self, mock_get, solver):
        """CAPCHA_NOT_READY (sin T) también debe continuar polling."""
        mock_get.return_value.json.side_effect = [
            {"status": 0, "request": "CAPCHA_NOT_READY"},
            {"status": 1, "request": "solution"},
        ]
        with patch("src.utils.captcha.asyncio.sleep"):
            result = await solver._wait_for_result_async("task_id", max_wait=20)
        assert result == "solution"


class TestCaptchaSolver:
    def test_init_no_key_raises(self):
        with patch.dict(os.environ, clear=True):
            with pytest.raises(CaptchaError):
                CaptchaSolver(api_key="")

    @patch("src.utils.captcha.requests.post")
    def test_solve_image_success(self, mock_post, solver):
        mock_post.return_value.json.return_value = {"status": 1, "request": "12345"}
        solver._wait_for_result = Mock(return_value="67890")
        assert solver.solve_image(b"fake-image-bytes") == "67890"

    @patch("src.utils.captcha.requests.post")
    def test_solve_image_fail(self, mock_post, solver):
        mock_post.return_value.json.return_value = {"status": 0, "request": "ERROR_IMAGE"}
        with pytest.raises(CaptchaError, match="Error enviando imagen"):
            solver.solve_image(b"fake-image-bytes")

    @patch("src.utils.captcha.requests.post")
    def test_solve_recaptcha_v2(self, mock_post, solver):
        mock_post.return_value.json.return_value = {"status": 1, "request": "12345"}
        solver._wait_for_result = Mock(return_value="recaptcha-token")
        assert solver.solve_recaptcha_v2("site_key", "https://test.com") == "recaptcha-token"

    def test_recaptcha_v2_manual(self, solver):
        assert solver.solve_recaptcha_v2("site_key", "https://test.com", auto=False) == "MANUAL"

    @patch("src.utils.captcha.requests.post")
    def test_solve_recaptcha_v3(self, mock_post, solver):
        mock_post.return_value.json.return_value = {"status": 1, "request": "12345"}
        solver._wait_for_result = Mock(return_value="v3-token")
        assert solver.solve_recaptcha_v3("site_key", "https://test.com") == "v3-token"

    @patch("src.utils.captcha.requests.get")
    def test_wait_for_result_success(self, mock_get, solver):
        mock_get.return_value.json.side_effect = [
            {"status": 0, "request": "CAPTCHA_NOT_READY"},
            {"status": 1, "request": "solution123"},
        ]
        with patch("src.utils.captcha.time.sleep"):
            result = solver._wait_for_result("task_id", max_wait=20)
        assert result == "solution123"
        assert mock_get.call_count == 2

    @patch("src.utils.captcha.requests.get")
    def test_wait_for_result_timeout(self, mock_get, solver):
        mock_get.return_value.json.return_value = {"status": 0, "request": "CAPTCHA_NOT_READY"}
        with patch("src.utils.captcha.time.sleep"):
            with pytest.raises(CaptchaError, match="Timeout"):
                solver._wait_for_result("task_id", max_wait=6)

    @patch("src.utils.captcha.requests.get")
    def test_wait_for_result_api_error(self, mock_get, solver):
        """Error de API: request no es CAPTCHA_NOT_READY."""
        mock_get.return_value.json.return_value = {"status": 0, "request": "ERROR_NO_SLOT_AVAILABLE"}
        with patch("src.utils.captcha.time.sleep"):
            with pytest.raises(CaptchaError, match="ERROR_NO_SLOT_AVAILABLE"):
                solver._wait_for_result("task_id", max_wait=30)

    @patch("src.utils.captcha.requests.get")
    def test_wait_for_result_retry_on_network_error(self, mock_get, solver):
        """Debe reintentar ante errores de red (Pilar 5 Resiliencia)."""
        ok_response = Mock()
        ok_response.json.return_value = {"status": 1, "request": "solution"}
        mock_get.side_effect = [requests.exceptions.ConnectionError("Network down"), ok_response]

        with patch("src.utils.captcha.time.sleep"):
            result = solver._wait_for_result("task_id", max_wait=30)

        assert result == "solution"
        assert mock_get.call_count == 2

    @patch("src.utils.captcha.requests.get")
    def test_wait_for_result_max_retries_exceeded(self, mock_get, solver):
        mock_get.side_effect = requests.exceptions.ConnectionError("Network down")

        with patch("src.utils.captcha.time.sleep"):
            with pytest.raises(CaptchaError, match="reintentos"):
                solver._wait_for_result("task_id", max_wait=120)
