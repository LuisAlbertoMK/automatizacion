"""Tests para src/tramites/predial_cdmx.py — Predial CDMX (consulta de adeudo)."""

from unittest.mock import AsyncMock, patch

import pytest

from src.exceptions import PredialError
from src.tramites.predial_cdmx import PredialCDMXModule

CUENTA_OK = "123456789012"


@pytest.fixture(autouse=True)
def _fast_sleep():
    """Evita asyncio.sleep real en predial_cdmx.py (sleep de 1s)."""
    with patch("asyncio.sleep", AsyncMock()):
        yield


@pytest.fixture
def mod():
    return PredialCDMXModule()


class TestConsultar:
    async def test_sin_datos(self, mod):
        with pytest.raises(PredialError, match="Se requiere cuenta predial o CL"):
            await mod.consultar()

    async def test_cuenta_invalida(self, mod):
        with pytest.raises(PredialError, match="Cuenta predial inválida"):
            await mod.consultar(cuenta="12345")

    async def test_exitoso_con_adeudo(self, mock_base, mod):
        """Consulta con adeudo: montos y ejercicios detectados."""
        mock_base['page'].content = AsyncMock(
            return_value="<html><body>DETALLE DEL ADEUDO</body></html>")
        mock_base['page'].inner_text = AsyncMock(
            return_value=("SU CUENTA PRESENTA ADEUDO\n"
                          "EJERCICIO 2023\nEJERCICIO 2024\nMonto: $2,345.67"))
        r = await mod.consultar(cuenta=CUENTA_OK)
        assert r["status"] == "ok"
        assert r["tramite"] == "predial_cdmx"
        assert r["cuenta"] == CUENTA_OK
        assert r["adeudo_actual"] is True
        assert r["sin_adeudo"] is False
        assert r["monto"] == "$2,345.67"
        assert "2023" in r["ejercicios"]
        assert "2024" in r["ejercicios"]
        assert r["adeudos"] and r["adeudos"][0]["monto"] == "$2,345.67"

    async def test_exitoso_sin_adeudo(self, mock_base, mod):
        mock_base['page'].content = AsyncMock(return_value="<html>sin adeudo</html>")
        mock_base['page'].inner_text = AsyncMock(
            return_value="SU CUENTA NO PRESENTA ADEUDO\nSin adeudo")
        r = await mod.consultar(cuenta=CUENTA_OK)
        assert r["status"] == "ok"
        assert r["sin_adeudo"] is True
        assert r["adeudo_actual"] is False
        assert r["monto"] == "$0.00"

    async def test_exitoso_por_clu(self, mock_base, mod):
        """CLÚ como alternativa: se llena el campo CLU, no la cuenta."""
        mock_base['page'].content = AsyncMock(return_value="<html>sin adeudo</html>")
        mock_base['page'].inner_text = AsyncMock(return_value="Sin adeudo")
        r = await mod.consultar(clu="CLU-0001-2024")
        assert r["status"] == "ok"
        assert r["clu"] == "CLU-0001-2024"
        assert r["cuenta"] == ""
        filled_values = [call.args[2] for call in mock_base['fill_field'].call_args_list]
        assert "CLU-0001-2024" in filled_values

    async def test_no_usa_password(self, mock_base, mod):
        """El flujo NO llena campos de password/login."""
        mock_base['page'].content = AsyncMock(return_value="<html></html>")
        mock_base['page'].inner_text = AsyncMock(return_value="")
        await mod.consultar(cuenta=CUENTA_OK)
        for call in mock_base['fill_field'].call_args_list:
            selectors = call.args[1]
            assert "password" not in " ".join(selectors)
            assert "login" not in " ".join(selectors)

    async def test_campo_no_encontrado(self, mock_base, mod):
        """fill_field falla  PredialError campo de cuenta predial."""
        mock_base['fill_field'].return_value = False
        with pytest.raises(PredialError, match="No se encontr"):
            await mod.consultar(cuenta=CUENTA_OK)


class TestParseo:
    async def test_sin_montos_ni_texto(self, mock_base, mod):
        """Respuesta sin datos → adeudo_actual None (desconocido)."""
        mock_base['page'].content = AsyncMock(return_value="<html>cargando...</html>")
        mock_base['page'].inner_text = AsyncMock(return_value="cargando")
        r = await mod.consultar(cuenta=CUENTA_OK)
        assert r["status"] == "ok"
        assert r["adeudo_actual"] is None
        assert r["adeudos"] == []
