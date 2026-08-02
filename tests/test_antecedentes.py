"""Tests para src/tramites/antecedentes.py — Antecedentes No Penales (flujo real sin registro)."""

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
    button_loc.first.text_content = AsyncMock(return_value=None)

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

    async def test_curp_invalida(self, mod):
        with pytest.raises(AntecedentesError, match="CURP inválida"):
            await mod.consultar(curp="CURPINVALIDA", correo="test@test.com")

    async def test_correo_invalido(self, mod):
        with pytest.raises(AntecedentesError, match="Correo electrónico inválido"):
            await mod.consultar(curp="ABCD123456HDFRRN08", correo="correo-invalido")

    async def test_exitoso(self, mock_base, mod):
        """Flujo completo sin registro — solicitud enviada."""
        _setup_happy(mock_base)
        r = await mod.consultar(
            curp="ABCD123456HDFRRN08",
            correo="test@test.com",
            nombre_tutor="Juan Perez",
            institucion="Secretaria",
            razon="Laboral",
        )
        assert r["status"] == "solicitado"
        assert r["curp"] == "ABCD123456HDFRRN08"
        assert r["correo"] == "test@test.com"
        assert "folio" in r
        assert "Pago $240 MXN" in r["nota"]

    async def test_curp_mayusculas(self, mock_base, mod):
        """CURP en minúsculas se normaliza a mayúsculas."""
        _setup_happy(mock_base)
        r = await mod.consultar(curp="abcd123456hdfrrn08", correo="test@test.com")
        assert r["curp"] == "ABCD123456HDFRRN08"

    async def test_folio_detectado(self, mock_base, mod):
        """Folio visible en la página → se registra en el resultado."""
        _setup_happy(mock_base, skip_locator=True)
        folio_loc = MagicMock()
        folio_loc.count = AsyncMock(return_value=1)
        folio_loc.first.text_content = AsyncMock(return_value="FOLIO: ABC123XYZ")
        mock_base['page'].locator = MagicMock(return_value=folio_loc)
        r = await mod.consultar(curp="ABCD123456HDFRRN08", correo="test@test.com")
        assert r["folio"] == "FOLIO: ABC123XYZ"

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
        r = await mod.consultar(curp="ABCD123456HDFRRN08", correo="test@test.com")
        assert r is not None

    async def test_con_recaptcha_sin_solver(self, mock_base, mod):
        """reCAPTCHA presente, solver=None → fallback manual."""
        _setup_happy(mock_base)
        r = await mod.consultar(curp="ABCD123456HDFRRN08", correo="test@test.com")
        assert r is not None
        mock_base['wait_for_recaptcha'].assert_called_once()

    async def test_con_recaptcha_audio(self, mock_base):
        """reCAPTCHA + solver con solve_recaptcha_v2_audio."""
        solver = MagicMock()
        solver.solve_recaptcha_v2_audio = AsyncMock(return_value="TOKEN123")
        mod = AntecedentesModule(captcha_solver=solver)
        mock_base['detect_site_key'].return_value = "6Lc_xxx"
        _setup_happy(mock_base)
        r = await mod.consultar(curp="ABCD123456HDFRRN08", correo="test@test.com")
        assert r is not None
        solver.solve_recaptcha_v2_audio.assert_called_once()

    async def test_audio_falla(self, mock_base):
        """Audio devuelve MANUAL → fallback a wait_for_recaptcha."""
        solver = MagicMock()
        solver.solve_recaptcha_v2_audio = AsyncMock(return_value="MANUAL")
        mod = AntecedentesModule(captcha_solver=solver)
        mock_base['detect_site_key'].return_value = "6Lc_xxx"
        _setup_happy(mock_base)
        r = await mod.consultar(curp="ABCD123456HDFRRN08", correo="test@test.com")
        assert r is not None
        mock_base['wait_for_recaptcha'].assert_called_once()


class TestFlujoSinRegistro:
    async def test_no_usa_password(self, mock_base, mod):
        """El flujo real NO usa registro/login — no se llenan campos de password."""
        _setup_happy(mock_base)
        await mod.consultar(curp="ABCD123456HDFRRN08", correo="test@test.com")
        for call in mock_base['fill_field'].call_args_list:
            selectors = call.args[1]
            assert "password" not in " ".join(selectors)

    async def test_llena_curp_primero(self, mock_base, mod):
        """El primer fill_field es la CURP."""
        _setup_happy(mock_base)
        await mod.consultar(curp="ABCD123456HDFRRN08", correo="test@test.com")
        first_call = mock_base['fill_field'].call_args_list[0]
        assert first_call.args[2] == "ABCD123456HDFRRN08"

    async def test_llena_solicitud(self, mock_base, mod):
        """Se llenan institución, razón y correo."""
        _setup_happy(mock_base)
        await mod.consultar(
            curp="ABCD123456HDFRRN08",
            correo="test@test.com",
            institucion="Secretaria",
            razon="Laboral",
        )
        filled_values = [call.args[2] for call in mock_base['fill_field'].call_args_list]
        assert "Secretaria" in filled_values
        assert "Laboral" in filled_values
        assert "test@test.com" in filled_values
