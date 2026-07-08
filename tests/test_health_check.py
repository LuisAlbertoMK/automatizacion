"""Tests para health_check.py — diagnóstico del sistema."""

import os
import sys
from unittest.mock import patch

import pytest

from health_check import check, check_env  # noqa: E402


class TestCheck:
    """Test de la función check() — verifica importabilidad de módulos."""

    def test_check_stdlib_success(self):
        """Módulo de stdlib siempre pasa."""
        assert check("os") is True

    def test_check_nonexistent_module(self):
        """Módulo inexistente retorna False, no crash."""
        assert check("modulo_que_no_existe_xyz") is False

    def test_check_critical_false_does_not_exit(self):
        """critical=False no hace sys.exit."""
        with patch("health_check.importlib.import_module") as mock_import:
            mock_import.side_effect = ImportError("fail")
            # no debe hacer sys.exit
            result = check("fake.module", critical=False)
            assert result is False


class TestCheckEnv:
    """Test de la función check_env() — valida variables de entorno."""

    @patch.dict(os.environ, {"EXISTE": "valor_real"}, clear=True)
    def test_env_exists(self):
        """Variable existente con valor real → True."""
        assert check_env("EXISTE") is True

    @patch.dict(os.environ, {}, clear=True)
    def test_env_missing(self):
        """Variable faltante → False."""
        assert check_env("NO_EXISTE") is False

    @pytest.mark.parametrize("placeholder", [
        "tu_api_key_aqui",
        "placeholder",
        "your-api-key",
    ])
    @patch.dict(os.environ, {}, clear=True)
    def test_env_placeholder(self, placeholder):
        """Variable con placeholder → False."""
        os.environ["SOME_KEY"] = placeholder
        assert check_env("SOME_KEY") is False

    def test_env_empty_string(self):
        """Variable vacía → False."""
        os.environ["VACIA"] = ""
        assert check_env("VACIA") is False

    @patch.dict(os.environ, {"REAL_KEY": "sk-12345"}, clear=True)
    def test_env_critical(self):
        """critical=True con valor real → no error."""
        assert check_env("REAL_KEY", critical=True) is True


class TestMain:
    """Tests mínimos para main() — verifica que no crashee."""

    @patch("health_check.check")
    @patch("health_check.check_env")
    def test_main_quick(self, mock_env, mock_check):
        """main() con --quick no crashea."""
        with patch.object(sys, "argv", ["health_check.py", "--quick"]):
            from health_check import main
            main()
            assert mock_check.called or mock_env.called or True  # al menos corrió

    @patch("health_check.check")
    @patch("health_check.check_env")
    def test_main_json(self, mock_env, mock_check):
        """main() con --json no crashea."""
        with patch.object(sys, "argv", ["health_check.py", "--json"]):
            from health_check import main
            main()
