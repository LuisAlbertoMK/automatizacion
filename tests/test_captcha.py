"""Tests unitarios para utils/captcha.py con 2captcha mockeado."""

import os
import sys
from unittest.mock import Mock, patch

import pytest
import requests

os.environ["CAPTCHA_API_KEY"] = "test_api_key_12345"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.captcha import CaptchaError, CaptchaSolver  # noqa: E402


@pytest.fixture
def solver():
    with patch.object(CaptchaSolver, "_verify_balance"):
        yield CaptchaSolver()


class TestCaptchaSolver:
    def test_init_no_key_raises(self):
        with patch.dict(os.environ, clear=True):
            with pytest.raises(CaptchaError):
                CaptchaSolver(api_key="")

    @patch("utils.captcha.requests.post")
    def test_solve_image_success(self, mock_post, solver):
        mock_post.return_value.json.return_value = {"status": 1, "request": "12345"}
        solver._wait_for_result = Mock(return_value="67890")
        assert solver.solve_image(b"fake-image-bytes") == "67890"

    @patch("utils.captcha.requests.post")
    def test_solve_image_fail(self, mock_post, solver):
        mock_post.return_value.json.return_value = {"status": 0, "request": "ERROR_IMAGE"}
        with pytest.raises(CaptchaError, match="Error enviando imagen"):
            solver.solve_image(b"fake-image-bytes")

    @patch("utils.captcha.requests.post")
    def test_solve_recaptcha_v2(self, mock_post, solver):
        mock_post.return_value.json.return_value = {"status": 1, "request": "12345"}
        solver._wait_for_result = Mock(return_value="recaptcha-token")
        assert solver.solve_recaptcha_v2("site_key", "https://test.com") == "recaptcha-token"

    def test_recaptcha_v2_manual(self, solver):
        assert solver.solve_recaptcha_v2("site_key", "https://test.com", auto=False) == "MANUAL"

    @patch("utils.captcha.requests.post")
    def test_solve_recaptcha_v3(self, mock_post, solver):
        mock_post.return_value.json.return_value = {"status": 1, "request": "12345"}
        solver._wait_for_result = Mock(return_value="v3-token")
        assert solver.solve_recaptcha_v3("site_key", "https://test.com") == "v3-token"

    @patch("utils.captcha.requests.get")
    def test_wait_for_result_success(self, mock_get, solver):
        mock_get.return_value.json.side_effect = [
            {"status": 0, "request": "CAPTCHA_NOT_READY"},
            {"status": 1, "request": "solution123"},
        ]
        with patch("utils.captcha.time.sleep"):
            result = solver._wait_for_result("task_id", max_wait=20)
        assert result == "solution123"
        assert mock_get.call_count == 2

    @patch("utils.captcha.requests.get")
    def test_wait_for_result_timeout(self, mock_get, solver):
        mock_get.return_value.json.return_value = {"status": 0, "request": "CAPTCHA_NOT_READY"}
        with patch("utils.captcha.time.sleep"):
            with pytest.raises(CaptchaError, match="Timeout"):
                solver._wait_for_result("task_id", max_wait=6)

    @patch("utils.captcha.requests.get")
    def test_wait_for_result_api_error(self, mock_get, solver):
        """Error de API: request no es CAPTCHA_NOT_READY."""
        mock_get.return_value.json.return_value = {"status": 0, "request": "ERROR_NO_SLOT_AVAILABLE"}
        with patch("utils.captcha.time.sleep"):
            with pytest.raises(CaptchaError, match="ERROR_NO_SLOT_AVAILABLE"):
                solver._wait_for_result("task_id", max_wait=30)

    @patch("utils.captcha.requests.get")
    def test_wait_for_result_retry_on_network_error(self, mock_get, solver):
        """Debe reintentar ante errores de red (Pilar 5 Resiliencia)."""
        ok_response = Mock()
        ok_response.json.return_value = {"status": 1, "request": "solution"}
        mock_get.side_effect = [requests.exceptions.ConnectionError("Network down"), ok_response]

        with patch("utils.captcha.time.sleep"):
            result = solver._wait_for_result("task_id", max_wait=30)

        assert result == "solution"
        assert mock_get.call_count == 2

    @patch("utils.captcha.requests.get")
    def test_wait_for_result_max_retries_exceeded(self, mock_get, solver):
        mock_get.side_effect = requests.exceptions.ConnectionError("Network down")

        with patch("utils.captcha.time.sleep"):
            with pytest.raises(CaptchaError, match="reintentos"):
                solver._wait_for_result("task_id", max_wait=120)
