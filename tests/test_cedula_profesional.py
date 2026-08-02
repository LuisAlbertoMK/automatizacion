"""Tests para src/tramites/cedula_profesional.py — Cédula Profesional SEP."""

from unittest.mock import AsyncMock, patch

import pytest

from src.exceptions import CedulaProfesionalError
from src.tramites.cedula_profesional import CedulaProfesionalModule

CURP_OK = "GARC850101HDFRRN09"


@pytest.fixture(autouse=True)
def _fast_sleep():
    """Evita asyncio.sleep real en cedula_profesional.py (sleep de 1s)."""
    with patch("asyncio.sleep", AsyncMock()):
        yield


@pytest.fixture
def mod():
    return CedulaProfesionalModule()


def _solr_docs():
    return [
        {"numero_cedula": ["1234567"], "titulo": ["ABOGADO"],
         "institucion": ["UNAM"], "estatus": ["VIGENTE"],
         "fechaExpedicion": ["2010"]},
    ]


class TestConsultar:
    async def test_sin_datos(self, mod):
        with pytest.raises(CedulaProfesionalError, match="Se requiere CURP o nombre"):
            await mod.consultar()

    async def test_curp_invalida(self, mod):
        with pytest.raises(CedulaProfesionalError, match="CURP inválida"):
            await mod.consultar(curp="CURPINVALIDA")

    async def test_curp_mayusculas(self, mock_base, mod):
        """CURP en minúsculas se normaliza a mayúsculas."""
        with patch.object(CedulaProfesionalModule, "_consulta_solr",
                          AsyncMock(return_value=[])) as solr:
            r = await mod.consultar(curp="garc850101hdfrrn09")
        assert r["status"] == "ok"
        assert solr.call_args.kwargs["curp"] == CURP_OK

    async def test_exitoso_solr(self, mock_base, mod):
        """HTTP-first: Solr responde → no se toca el navegador."""
        with patch.object(CedulaProfesionalModule, "_consulta_solr",
                          AsyncMock(return_value=_solr_docs())):
            r = await mod.consultar(curp=CURP_OK)
        assert r["status"] == "ok"
        assert r["tramite"] == "cedula_profesional"
        assert r["fuente"] == "solr"
        assert r["total"] == 1
        assert r["cedulas"][0]["numero"] == "1234567"
        assert r["cedulas"][0]["titulo"] == "ABOGADO"
        mock_base['goto'].assert_not_called()

    async def test_solr_vacio_no_usa_browser(self, mock_base, mod):
        """Solr OK sin resultados → respuesta vacía sin navegador."""
        with patch.object(CedulaProfesionalModule, "_consulta_solr",
                          AsyncMock(return_value=[])):
            r = await mod.consultar(curp=CURP_OK)
        assert r["status"] == "ok"
        assert r["total"] == 0
        assert "nota" in r
        mock_base['goto'].assert_not_called()

    async def test_exitoso_navegador(self, mock_base, mod):
        """Fallback: Solr no disponible → flujo de navegador."""
        with patch.object(CedulaProfesionalModule, "_consulta_solr",
                          AsyncMock(return_value=None)):
            mock_base['page'].content = AsyncMock(
                return_value="<html>CÉDULA: 1234567<br>TÍTULO: LICENCIADO</html>")
            mock_base['page'].inner_text = AsyncMock(
                return_value="CÉDULA: 1234567\nTÍTULO: LICENCIADO\nINSTITUCIÓN: IPN\nESTATUS: VIGENTE")
            r = await mod.consultar(curp=CURP_OK)
        assert r["status"] == "ok"
        assert r["fuente"] == "navegador"
        assert r["total"] == 1
        assert r["cedulas"][0]["titulo"] == "LICENCIADO"
        mock_base['goto'].assert_called_once()
        mock_base['fill_field'].assert_called_once()

    async def test_consulta_por_nombre(self, mock_base, mod):
        """Sin CURP, consulta por nombre/apellidos."""
        with patch.object(CedulaProfesionalModule, "_consulta_solr",
                          AsyncMock(return_value=[])) as solr:
            r = await mod.consultar(nombre="JUAN", apellido_paterno="PEREZ")
        assert r["status"] == "ok"
        assert solr.call_args.kwargs["nombre"] == "JUAN"
        assert solr.call_args.kwargs["curp"] == ""

    async def test_no_usa_password(self, mock_base, mod):
        """El flujo NO llena campos de password/login."""
        with patch.object(CedulaProfesionalModule, "_consulta_solr",
                          AsyncMock(return_value=None)):
            mock_base['page'].content = AsyncMock(return_value="<html></html>")
            mock_base['page'].inner_text = AsyncMock(return_value="")
            await mod.consultar(curp=CURP_OK)
        for call in mock_base['fill_field'].call_args_list:
            selectors = call.args[1]
            assert "password" not in " ".join(selectors)
            assert "login" not in " ".join(selectors)


class TestConsultaSolr:
    async def test_http_error_devuelve_none(self):
        """Error HTTP en Solr → None (gatilla fallback a navegador)."""
        mod = CedulaProfesionalModule()
        with patch("src.tramites.cedula_profesional.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.side_effect = Exception("reset")
            docs = await mod._consulta_solr(curp=CURP_OK)
        assert docs is None

    async def test_ok_devuelve_docs(self):
        mod = CedulaProfesionalModule()
        with patch("src.tramites.cedula_profesional.requests.get") as mock_get:
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.json.return_value = {
                "response": {"docs": [{"cedula": ["9999999"]}]}}
            docs = await mod._consulta_solr(curp=CURP_OK)
        assert docs == [{"cedula": ["9999999"]}]
        params = mock_get.call_args.kwargs["params"]
        assert params["q"] == f'curp:"{CURP_OK}"'
