"""Tests para src/tramites/curp.py — Consulta CURP en gob.mx/curp"""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exceptions import CURPError
from src.tramites.curp import CURPModule, ESTADOS


def _setup_happy(mock_base, prefill_content=True):
    """Configura mocks para flujo exitoso de CURP."""
    page = mock_base['page']
    # _enviar_busqueda necesita page.locator que devuelva count>0
    loc = MagicMock()
    loc.count = AsyncMock(return_value=1)
    page.locator = MagicMock(return_value=loc)
    # get_by_role fallback bien configurado
    btn = MagicMock()
    btn.count = AsyncMock(return_value=0)  # que no interfiera
    page.get_by_role = MagicMock(return_value=btn)
    # Content con CURP para _extraer_resultado
    if prefill_content:
        page.content.return_value = (
            '<html>Nombre(s): Juan Primer apellido: Pérez '
            'CURP: GALJ800101HDFXXXX0</html>'
        )
        page.inner_text.return_value = (
            "Nombre(s): Juan Primer apellido: Pérez"
        )


class TestConsultar:
    async def test_sin_curp_ni_datos(self):
        mod = CURPModule()
        with pytest.raises(CURPError, match="Se requiere curp o datos personales"):
            await mod.consultar()

    async def test_sin_curp_explicito(self):
        mod = CURPModule()
        with pytest.raises(CURPError, match="Se requiere curp o datos personales"):
            await mod.consultar(curp="")

    async def test_exitoso_por_curp(self, mock_base):
        """Happy path: consulta por CURP directa."""
        _setup_happy(mock_base)
        mod = CURPModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r["curp"] == "GALJ800101HDFXXXX0"
        assert r["pdf_path"] == "test.pdf"

    async def test_exitoso_por_datos(self, mock_base):
        """Happy path: consulta por datos personales."""
        _setup_happy(mock_base)
        mod = CURPModule()
        r = await mod.consultar(datos={
            "nombre": "Juan", "primer_apellido": "Pérez",
            "fecha_nacimiento": "01/01/1980",
        })
        assert r["curp"] == "GALJ800101HDFXXXX0"
        assert r["pdf_path"] == "test.pdf"

    async def test_pdf_no_descargado(self, mock_base):
        _setup_happy(mock_base)
        mock_base['download_pdf'].return_value = None
        mod = CURPModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r["pdf_path"] is None

    async def test_error_propaga(self, mock_base):
        """CURPModule.consultar NO envuelve errores — ValueError propaga."""
        mock_base['goto'].side_effect = ValueError("fail")
        mod = CURPModule()
        with pytest.raises(ValueError, match="fail"):
            await mod.consultar(curp="GALJ800101HDFXXXX0")

    async def test_curp_error_propaga(self, mock_base):
        """CURPError dentro de _run → propaga sin wrapper."""
        mock_base['goto'].side_effect = CURPError("específico")
        mod = CURPModule()
        with pytest.raises(CURPError, match="específico"):
            await mod.consultar(curp="GALJ800101HDFXXXX0")


class TestConsultaPorCurp:
    async def test_ok(self, mock_base):
        """click_first + fill_field OK → CURP ingresada."""
        _setup_happy(mock_base)
        mod = CURPModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r["curp"] == "GALJ800101HDFXXXX0"

    async def test_fill_field_falla(self, mock_base):
        """fill_field falla → find_visible_inputs fallback."""
        _setup_happy(mock_base)
        mock_base['fill_field'].return_value = False
        inp = {"name": "curp", "id": "", "placeholder": "", "element": MagicMock()}
        inp["element"].fill = AsyncMock()
        mock_base['find_visible_inputs'].return_value = [inp]

        mod = CURPModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        inp["element"].fill.assert_called_once()

    async def test_todo_falla(self, mock_base):
        """fill_field + find_visible_inputs fallan → CURPError."""
        _setup_happy(mock_base)
        mock_base['fill_field'].return_value = False
        mock_base['find_visible_inputs'].return_value = []

        mod = CURPModule()
        with pytest.raises(CURPError, match="No se encontró el campo de CURP"):
            await mod.consultar(curp="GALJ800101HDFXXXX0")

    async def test_find_visible_exception(self, mock_base):
        """find_visible_inputs lanza excepción → CURPError."""
        _setup_happy(mock_base)
        mock_base['fill_field'].return_value = False
        mock_base['find_visible_inputs'].side_effect = Exception("fail")

        mod = CURPModule()
        with pytest.raises(CURPError, match="No se encontró el campo de CURP"):
            await mod.consultar(curp="GALJ800101HDFXXXX0")


class TestConsultaPorDatos:
    async def test_ok_completo(self, mock_base):
        """Todos los campos de datos personales."""
        _setup_happy(mock_base)
        mod = CURPModule()
        r = await mod.consultar(datos={
            "nombre": "Juan", "primer_apellido": "Pérez",
            "segundo_apellido": "López",
            "fecha_nacimiento": "01/01/1980",
            "sexo": "H", "estado": "CIUDAD DE MEXICO",
        })
        assert r is not None

    async def test_solo_obligatorios(self, mock_base):
        """Solo nombre y apellido paterno."""
        _setup_happy(mock_base)
        mod = CURPModule()
        r = await mod.consultar(datos={
            "nombre": "María",
            "primer_apellido": "García",
        })
        assert r is not None

    async def test_sexo_select(self, mock_base):
        """page.locator('select[name=\"sexo\"]') detectado."""
        _setup_happy(mock_base)
        loc = MagicMock()
        loc.count = AsyncMock(return_value=1)
        mock_base['page'].locator = MagicMock(return_value=loc)
        mod = CURPModule()
        r = await mod.consultar(datos={
            "nombre": "Ana", "primer_apellido": "Luna",
            "sexo": "M",
        })
        assert r is not None

    async def test_estado_encontrado(self, mock_base):
        """Estado con valor válido."""
        _setup_happy(mock_base)
        loc = MagicMock()
        loc.count = AsyncMock(return_value=1)
        mock_base['page'].locator = MagicMock(return_value=loc)
        mod = CURPModule()
        r = await mod.consultar(datos={
            "nombre": "Luis", "primer_apellido": "Sol",
            "estado": "NUEVO LEON",
        })
        assert r is not None

    async def test_estado_con_mexico(self, mock_base):
        """Estado 'MÉXICO' se normaliza a 'MEXICO'."""
        _setup_happy(mock_base)
        loc = MagicMock()
        loc.count = AsyncMock(return_value=1)
        mock_base['page'].locator = MagicMock(return_value=loc)
        mod = CURPModule()
        r = await mod.consultar(datos={
            "nombre": "Luis", "primer_apellido": "Sol",
            "estado": "MÉXICO",
        })
        assert r is not None
        # select_option debe recibir "MC"
        mock_base['page'].select_option.assert_called_with(
            "select[name='estado']", "MC"
        )

    async def test_sexo_select_exception(self, mock_base):
        """page.locator falla → debug + continúa."""
        _setup_happy(mock_base, prefill_content=False)
        # _enviar_busqueda falla x locator → get_by_role fallback necesita funcionar
        btn = MagicMock()
        btn.count = AsyncMock(return_value=1)
        btn.click = AsyncMock()
        mock_base['page'].get_by_role = MagicMock(return_value=btn)
        mock_base['page'].locator.side_effect = Exception("fail")
        mod = CURPModule()
        r = await mod.consultar(datos={
            "nombre": "Ana", "primer_apellido": "Luna",
        })
        assert r is not None

    async def test_estado_no_encontrado(self, mock_base):
        """Estado no en ESTADOS → default MC."""
        _setup_happy(mock_base, prefill_content=False)
        loc = MagicMock()
        loc.count = AsyncMock(return_value=0)
        mock_base['page'].locator = MagicMock(return_value=loc)
        # _enviar_busqueda necesita fallback
        btn = MagicMock()
        btn.count = AsyncMock(return_value=1)
        btn.click = AsyncMock()
        mock_base['page'].get_by_role = MagicMock(return_value=btn)
        mod = CURPModule()
        r = await mod.consultar(datos={
            "nombre": "Luis", "primer_apellido": "Sol",
            "estado": "INEXISTENTE",
        })
        assert r is not None

    async def test_estado_selector_no_disponible(self, mock_base):
        """page.select_option falla → debug + continúa."""
        _setup_happy(mock_base, prefill_content=False)
        loc = MagicMock()
        loc.count = AsyncMock(return_value=1)
        mock_base['page'].locator = MagicMock(return_value=loc)
        mock_base['page'].select_option.side_effect = Exception("no option")
        # _enviar_busqueda necesita fallback
        btn = MagicMock()
        btn.count = AsyncMock(return_value=1)
        btn.click = AsyncMock()
        mock_base['page'].get_by_role = MagicMock(return_value=btn)
        mod = CURPModule()
        r = await mod.consultar(datos={
            "nombre": "Luis", "primer_apellido": "Sol",
            "estado": "SONORA",
        })
        assert r is not None


class TestEnviarBusqueda:
    async def test_ok_normal(self, mock_base):
        """Botón encontrado por selector → click."""
        _setup_happy(mock_base)
        mod = CURPModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r is not None

    async def test_ok_fallback_role(self, mock_base):
        """Selectores fallan → get_by_role fallback."""
        loc = MagicMock()
        loc.count = AsyncMock(return_value=0)
        mock_base['page'].locator = MagicMock(return_value=loc)

        btn = MagicMock()
        btn.count = AsyncMock(return_value=1)
        btn.click = AsyncMock()
        mock_base['page'].get_by_role = MagicMock(return_value=btn)

        mod = CURPModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r is not None
        btn.click.assert_called_once()

    async def test_todo_falla(self, mock_base):
        """Ningún botón encontrado → CURPError."""
        loc = MagicMock()
        loc.count = AsyncMock(return_value=0)
        mock_base['page'].locator = MagicMock(return_value=loc)
        btn = MagicMock()
        btn.count = AsyncMock(return_value=0)
        mock_base['page'].get_by_role = MagicMock(return_value=btn)

        mod = CURPModule()
        with pytest.raises(CURPError, match="No se encontró el botón de búsqueda"):
            await mod.consultar(curp="GALJ800101HDFXXXX0")

    async def test_exception_continua(self, mock_base):
        """locator.count lanza excepción → debug + continúa."""
        loc = MagicMock()
        loc.count = AsyncMock(side_effect=[Exception("fail"), Exception("fail"), 1])
        mock_base['page'].locator = MagicMock(return_value=loc)
        mock_base['page'].get_by_role = MagicMock()  # avoid fallback interference
        mod = CURPModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r is not None


class TestExtraerResultado:
    CURP_EN_HTML = "<html>Nombre(s): Juan Primer apellido: Pérez CURP: GALJ800101HDFXXXX0</html>"

    async def test_extraer_desde_html(self, mock_base):
        """Extrae CURP y nombre del HTML."""
        _setup_happy(mock_base)
        mock_base['page'].content.return_value = self.CURP_EN_HTML
        # NOTA: _campo usa regex lazy +? hasta \n; cada campo en su propia línea
        mock_base['page'].inner_text.return_value = (
            "Nombre(s): Juan\nPrimer apellido: Pérez\nSexo: HOMBRE\n"
            "Fecha de nacimiento: 01/01/1980\nNacionalidad: MEXICANA\n"
            "Entidad de nacimiento: CIUDAD DE MEXICO"
        )
        mod = CURPModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r["curp"] == "GALJ800101HDFXXXX0"
        assert "Juan" in r["nombre"]
        assert r["sexo"] == "HOMBRE"
        assert r["fecha_nacimiento"] == "01/01/1980"

    async def test_sin_datos_en_html(self, mock_base):
        """HTML sin datos → todos vacíos."""
        _setup_happy(mock_base)
        mock_base['page'].content.return_value = "<html>Sin información</html>"
        mock_base['page'].inner_text.return_value = "Sin información"
        mod = CURPModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r["curp"] == "DESCONOCIDA"

    async def test_con_ocr_fallback(self, mock_base):
        """HTML sin datos + OCR disponible → OCR extrae."""
        _setup_happy(mock_base)
        mock_base['page'].content.return_value = "<html>Sin info</html>"
        mock_base['page'].inner_text.return_value = "Sin info"

        fake_ocr = MagicMock()
        fake_ocr.extract_from_screenshot.return_value = {
            "curp": "GALJ800101HDFXXXX0",
            "raw_text": "Nombre(s): Juan\nPrimer apellido: Pérez",
        }
        mod = CURPModule(use_ocr=True)
        mod.ocr = fake_ocr
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r["curp"] == "GALJ800101HDFXXXX0"
        assert "Juan" in r["nombre"]

    async def test_ocr_fallback_sin_nombre(self, mock_base):
        """OCR extrae CURP pero no nombre → nombre vacío."""
        _setup_happy(mock_base)
        mock_base['page'].content.return_value = "<html>Sin info</html>"
        mock_base['page'].inner_text.return_value = "Sin info"

        fake_ocr = MagicMock()
        fake_ocr.extract_from_screenshot.return_value = {
            "curp": "GALJ800101HDFXXXX0",
            "raw_text": "Sin datos legibles",
        }
        mod = CURPModule(use_ocr=True)
        mod.ocr = fake_ocr
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r["curp"] == "GALJ800101HDFXXXX0"

    async def test_ocr_exception(self, mock_base):
        """OCR falla con excepción → warn + continúa."""
        _setup_happy(mock_base)
        mock_base['page'].content.return_value = "<html>Sin info</html>"
        mock_base['page'].inner_text.return_value = "Sin info"

        fake_ocr = MagicMock()
        fake_ocr.extract_from_screenshot.side_effect = ValueError("ocr fail")
        mod = CURPModule(use_ocr=True)
        mod.ocr = fake_ocr
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r["curp"] == "DESCONOCIDA"
        mock_base['warn'].assert_called_once()

    async def test_ocr_disabled(self, mock_base):
        """use_ocr=False → no intenta OCR."""
        _setup_happy(mock_base)
        mock_base['page'].content.return_value = "<html>Sin info</html>"
        mock_base['page'].inner_text.return_value = "Sin info"
        mod = CURPModule(use_ocr=False)
        mod.ocr = MagicMock()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r["curp"] == "DESCONOCIDA"

    async def test_estados_dict(self):
        """ESTADOS tiene las 32 entidades + NE."""
        assert len(ESTADOS) == 33
        assert ESTADOS["CIUDAD DE MEXICO"] == "DF"
        assert ESTADOS["NACIDO EN EXTRANJERO"] == "NE"

    async def test_screenshot_exception(self, mock_base):
        """Screenshot en _run falla → debug + continúa."""
        _setup_happy(mock_base)
        mock_base['page'].screenshot.side_effect = Exception("no img")
        mod = CURPModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r is not None

    async def test_campo_con_sexo_y_datos_extra(self, mock_base):
        """Extrae todos los campos opcionales."""
        _setup_happy(mock_base)
        mock_base['page'].content.return_value = "<html>Datos</html>"
        mock_base['page'].inner_text.return_value = (
            "Nombre(s): Juan\nPrimer apellido: Pérez\nSegundo apellido: López\n"
            "Sexo: HOMBRE\nFecha de nacimiento: 01/01/1980\n"
            "Nacionalidad: MEXICANA\nEntidad de nacimiento: CDMX\n"
            "Documento probatorio: ACTA DE NACIMIENTO"
        )
        mod = CURPModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert r["sexo"] == "HOMBRE"
        assert r["fecha_nacimiento"] == "01/01/1980"
        assert r["nacionalidad"] == "MEXICANA"
        assert r["entidad_nacimiento"] == "CDMX"
        assert r["documento_probatorio"] == "ACTA DE NACIMIENTO"
