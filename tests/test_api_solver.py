"""Tests para api._get_solver — sin autouse fixture que parchea _get_solver."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestGetSolver:
    """Lines 117-127: _get_solver con diferentes configuraciones."""

    def test_solver_with_valid_key(self):
        with patch.dict(os.environ, {"CAPTCHA_API_KEY": "valid_key_123"}):
            import importlib

            import api
            api_module = importlib.reload(api)
            with patch.object(api_module, "CaptchaSolver") as mock_solver:
                mock_solver.return_value = "solver_instance"
                result = api_module._get_solver()
        assert result == "solver_instance"
        mock_solver.assert_called_once_with("valid_key_123")

    def test_solver_with_default_key_falls_to_free(self):
        with patch.dict(os.environ, {"CAPTCHA_API_KEY": "tu_api_key_aqui"}):
            import importlib

            import api
            api_module = importlib.reload(api)
            with patch("utils.free_captcha.FreeCaptchaSolver", return_value="free_solver"):
                result = api_module._get_solver()
        assert result == "free_solver"

    def test_solver_with_empty_key_falls_to_free(self):
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            import api
            api_module = importlib.reload(api)
            with patch("utils.free_captcha.FreeCaptchaSolver", return_value="free_solver"):
                result = api_module._get_solver()
        assert result == "free_solver"

    def test_solver_captcha_error_falls_to_free(self):
        from utils.captcha import CaptchaError
        with patch.dict(os.environ, {"CAPTCHA_API_KEY": "valid_key"}):
            import importlib

            import api
            api_module = importlib.reload(api)
            with patch.object(api_module, "CaptchaSolver", side_effect=CaptchaError("fail")):
                with patch("utils.free_captcha.FreeCaptchaSolver", return_value="free_solver"):
                    result = api_module._get_solver()
        assert result == "free_solver"

    def test_solver_all_fail_returns_none(self):
        from utils.captcha import CaptchaError
        with patch.dict(os.environ, {"CAPTCHA_API_KEY": "valid_key"}):
            import importlib

            import api
            api_module = importlib.reload(api)
            with patch.object(api_module, "CaptchaSolver", side_effect=CaptchaError("fail")):
                with patch("utils.free_captcha.FreeCaptchaSolver", side_effect=ImportError("no module")):
                    result = api_module._get_solver()
        assert result is None
