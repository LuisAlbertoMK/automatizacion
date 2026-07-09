"""Tests para src/tramites/antecedentes.py — Antecedentes No Penales."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exceptions import AntecedentesError
from src.tramites.antecedentes import AntecedentesModule


@pytest.fixture(autouse=True)
def _fast_sleep():
    """Evita asyncio.sleep real en antecedentes.py (tiene sleeps de 1-3s)."""
    with patch("asyncio.sleep", AsyncMock()):
        yield


@pytest.fixture
def mod():
    return AntecedentesModule()


def _smart_locator(*, recaptcha_count=1):
    """Side-effect factory: recaptcha selectors vs button selectors."""
    recaptcha_loc = MagicMock()
    recaptcha_loc.count = AsyncMock(return_value=recaptcha_count)
    button_loc = MagicMock()
    button_loc.count = AsyncMock(return_value=1)
    button_loc.first.click = AsyncMock()

    def _side_effect(sel):
        if 'recaptcha' in str(sel).lower():
            return recaptcha_loc
        return button_loc

    return _side_effect


def _setup_happy(mock_base, skip_locator=False):
    """Configura mocks para flujo exitoso."""
    page = mock_base['page']
    if not skip_locator:
        page.locator = MagicMock(side_effect=_smart_locator(recaptcha_count=1))


class TestConsultar:
    async def test_sin_curp(self, mod):
        with pytest.raises(AntecedentesError, match="Se requieren CURP y correo"):
            await mod.consultar(curp="", correo="")

    async def test_sin_correo(self, mod):
        with pytest.raises(AntecedentesError, match="Se requieren CURP y correo"):
            await mod.consultar(curp="ABCD123456HDFRRN08", correo="")

    async def test_exitoso_con_password(self, mock_base, mod):
        """Login con cuenta existente."""
        _setup_happy(mock_base)
        r = await mod.consultar(
            curp="ABCD123456HDFRRN08",
            correo="test@test.com",
            password="mypassword",
        )
        assert r["constancia_path"] == "test.pdf"
        assert r["curp"] == "ABCD123456HDFRRN08"
        assert "password" not in r

    async def test_exitoso_sin_password(self, mock_base, mod):
        """Registro de nueva cuenta."""
        _setup_happy(mock_base)
        with patch("src.tramites.antecedentes.AntecedentesModule._guardar_credenciales"):
            r = await mod.consultar(
                curp="ABCD123456HDFRRN08",
                correo="test@test.com",
                datos_personales={"nombre": "Juan"},
            )
        assert r["constancia_path"] == "test.pdf"
        assert "_nueva_password" in r

    async def test_registro_con_password_en_datos(self, mock_base, mod):
        """Registro con password en datos_personales."""
        _setup_happy(mock_base)
        with patch("src.tramites.antecedentes.AntecedentesModule._guardar_credenciales"):
            r = await mod.consultar(
                curp="ABCD123456HDFRRN08",
                correo="test@test.com",
                datos_personales={"nombre": "Juan", "password": "MiPass123!"},
            )
        assert r["constancia_path"] == "test.pdf"
        assert "_nueva_password" in r

    async def test_sin_datos_registro(self, mock_base, mod):
        """Registro sin datos_personales → no se llenan campos."""
        _setup_happy(mock_base)
        r = await mod.consultar(
            curp="ABCD123456HDFRRN08",
            correo="test@test.com",
        )
        assert r["constancia_path"] == "test.pdf"

    async def test_pdf_no_descargado(self, mock_base, mod):
        _setup_happy(mock_base)
        mock_base['download_pdf'].return_value = None
        r = await mod.consultar(
            curp="ABCD123456HDFRRN08",
            correo="test@test.com",
            password="pass",
        )
        assert r["constancia_path"] is None

    async def test_error_generico(self, mock_base, mod):
        """"consultar" no tiene try/except, el error se propaga tal cual."""
        mock_base['page'].goto.side_effect = ValueError("fail")
        with pytest.raises(ValueError):
            await mod.consultar(curp="ABCD123456HDFRRN08", correo="test@test.com")


class TestResolverRecaptcha:
    async def test_sin_recaptcha(self, mock_base, mod):
        """No hay iframe reCAPTCHA → return directo."""
        _setup_happy(mock_base, skip_locator=True)
        mock_base['page'].locator = MagicMock(side_effect=_smart_locator(recaptcha_count=0))
        r = await mod.consultar(curp="ABCD123456HDFRRN08", correo="test@test.com",
                                password="pass")
        assert r is not None

    async def test_con_recaptcha_sin_solver(self, mock_base, mod):
        """reCAPTCHA presente, solver=None → fallback manual."""
        _setup_happy(mock_base)
        r = await mod.consultar(curp="ABCD123456HDFRRN08", correo="test@test.com",
                                password="pass")
        assert r is not None
        mock_base['wait_for_recaptcha'].assert_called_once()

    async def test_con_recaptcha_audio(self, mock_base):
        """reCAPTCHA + solver con solve_recaptcha_v2_audio."""
        solver = MagicMock()
        solver.solve_recaptcha_v2_audio = AsyncMock(return_value="TOKEN123")
        mod = AntecedentesModule(captcha_solver=solver)
        mock_base['detect_site_key'].return_value = "6Lc_xxx"
        _setup_happy(mock_base)
        r = await mod.consultar(curp="ABCD123456HDFRRN08", correo="test@test.com",
                                password="pass")
        assert r is not None
        solver.solve_recaptcha_v2_audio.assert_called_once()

    async def test_audio_falla(self, mock_base):
        """Audio devuelve MANUAL → fallback a wait_for_recaptcha."""
        solver = MagicMock()
        solver.solve_recaptcha_v2_audio = AsyncMock(return_value="MANUAL")
        mod = AntecedentesModule(captcha_solver=solver)
        mock_base['detect_site_key'].return_value = "6Lc_xxx"
        _setup_happy(mock_base)
        r = await mod.consultar(curp="ABCD123456HDFRRN08", correo="test@test.com",
                                password="pass")
        assert r is not None
        mock_base['wait_for_recaptcha'].assert_called_once()


class TestGuardarCredenciales:
    async def test_ok(self, mock_base, mod):
        _setup_happy(mock_base)
        with patch("src.utils.storage.save_profile") as mock_save:
            r = await mod.consultar(
                curp="ABCD123456HDFRRN08",
                correo="test@test.com",
                datos_personales={"nombre": "Juan"},
            )
            mock_save.assert_called_once()

    async def test_falla(self, mock_base, mod):
        _setup_happy(mock_base)
        with patch("src.utils.storage.save_profile",
                   side_effect=Exception("storage error")):
            r = await mod.consultar(
                curp="ABCD123456HDFRRN08",
                correo="test@test.com",
                datos_personales={"nombre": "Juan"},
            )
            assert r is not None  # warn pero no falla


class TestLogin:
    async def test_click_exception(self, mock_base, mod):
        """page.click en login falla → except + continúa."""
        mock_base['page'].click.side_effect = Exception("click error")
        _setup_happy(mock_base)
        r = await mod.consultar(curp="ABCD123456HDFRRN08", correo="test@test.com",
                                password="pass")
        assert r is not None
