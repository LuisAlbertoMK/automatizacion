"""Tests para api._get_solver — sin autouse fixture que parchea _get_solver."""

import os
from unittest.mock import patch


class TestGetSolver:
    """Lines 117-127: _get_solver con diferentes configuraciones."""

    def test_solver_with_valid_key(self):
        with patch.dict(os.environ, {"CAPTCHA_API_KEY": "valid_key_123"}):
            import importlib

            from src import api
            api_module = importlib.reload(api)
            with patch.object(api_module, "CaptchaSolver") as mock_solver:
                mock_solver.return_value = "solver_instance"
                result = api_module._get_solver()
        assert result == "solver_instance"
        mock_solver.assert_called_once_with("valid_key_123")

    def test_solver_with_default_key_falls_to_free(self):
        with patch.dict(os.environ, {"CAPTCHA_API_KEY": "tu_api_key_aqui"}):
            import importlib

            from src import api
            api_module = importlib.reload(api)
            with patch("src.utils.free_captcha.FreeCaptchaSolver", return_value="free_solver"):
                result = api_module._get_solver()
        assert result == "free_solver"

    def test_solver_with_empty_key_falls_to_free(self):
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            from src import api
            api_module = importlib.reload(api)
            with patch("src.utils.free_captcha.FreeCaptchaSolver", return_value="free_solver"):
                result = api_module._get_solver()
        assert result == "free_solver"

    def test_solver_captcha_error_falls_to_free(self):
        from src.utils.captcha import CaptchaError
        with patch.dict(os.environ, {"CAPTCHA_API_KEY": "valid_key"}):
            import importlib

            from src import api
            api_module = importlib.reload(api)
            with patch.object(api_module, "CaptchaSolver", side_effect=CaptchaError("fail")):
                with patch("src.utils.free_captcha.FreeCaptchaSolver", return_value="free_solver"):
                    result = api_module._get_solver()
        assert result == "free_solver"

    def test_solver_all_fail_returns_none(self):
        from src.utils.captcha import CaptchaError
        with patch.dict(os.environ, {"CAPTCHA_API_KEY": "valid_key"}):
            import importlib

            from src import api
            api_module = importlib.reload(api)
            with patch.object(api_module, "CaptchaSolver", side_effect=CaptchaError("fail")):
                with patch("src.utils.free_captcha.FreeCaptchaSolver", side_effect=ImportError("no module")):
                    result = api_module._get_solver()
        assert result is None
