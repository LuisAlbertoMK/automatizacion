"""Tests para src/api.py — API REST FastAPI con TestClient."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="pip install -e '.[web]'")
from fastapi.testclient import TestClient

from src.api import app  # noqa: E402

# ── Fixture autouse para toda la clase: mockea módulos reales ─────────────────

@pytest.fixture(autouse=True)
def _mock_browser_modules():
    """Parchea _get_solver, CURPModule y NSSModule en TODOS los tests de API.
    
    Sin esto, los handlers intentan lanzar Playwright y cuelgan.
    Cada test puede sobreescribir parches específicos.
    """
    with patch("src.api._get_solver") as mock_solver, \
         patch("src.api.CURPModule") as mock_curp, \
         patch("src.api.NSSModule") as mock_nss:
        mock_solver.return_value = MagicMock()
        for mock_mod in (mock_curp, mock_nss):
            instance = AsyncMock()
            instance.consultar = AsyncMock(side_effect=Exception("Mocked module"))
            mock_mod.return_value = instance
        yield


class TestRoot:
    def test_root_returns_info(self):
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert "version" in data
        assert "endpoints" in data

    def test_root_lists_endpoints(self):
        client = TestClient(app)
        data = client.get("/").json()
        endpoints = data["endpoints"]
        keys_str = " ".join(endpoints.keys())
        assert "/health" in keys_str
        assert "/curp" in keys_str
        assert "/nss" in keys_str


class TestHealth:
    def test_health_ok(self):
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestPerfiles:
    @patch("src.api.list_profiles", return_value=[])
    def test_listar_perfiles_empty(self, mock_list):
        client = TestClient(app)
        response = client.get("/perfiles")
        assert response.status_code == 200
        assert response.json() == {"perfiles": []}

    @patch("src.api.list_profiles", return_value=["juan", "maria"])
    def test_listar_perfiles_with_data(self, mock_list):
        client = TestClient(app)
        response = client.get("/perfiles")
        assert response.status_code == 200
        assert response.json() == {"perfiles": ["juan", "maria"]}

    @patch("src.api.save_profile")
    def test_guardar_perfil(self, mock_save):
        client = TestClient(app)
        response = client.post("/perfiles", json={
            "alias": "test_user",
            "curp": "GARC850101HDFRRNA3",
            "correo": "test@test.com",
        })
        assert response.status_code == 200
        assert response.json()["alias"] == "test_user"
        assert response.json()["success"] is True
        mock_save.assert_called_once()


class TestCurp:
    def test_consultar_curp_con_error(self):
        """El mock default retorna error → 500."""
        client = TestClient(app)
        response = client.post("/curp", json={"curp": "GALJ800101HDFRRNA9"})
        assert response.status_code == 500

    @patch("src.api._get_solver")
    @patch("src.api.CURPModule")
    def test_consultar_curp_exitoso(self, mock_mod_cls, mock_solver):
        mock_solver.return_value = MagicMock()
        mock_instance = AsyncMock()
        mock_instance.consultar = AsyncMock(return_value={
            "curp": "GALJ800101HDFRRNA9",
            "nombre": "JUAN",
        })
        mock_mod_cls.return_value = mock_instance

        client = TestClient(app)
        response = client.post("/curp", json={"curp": "GALJ800101HDFRRNA9"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["curp"] == "GALJ800101HDFRRNA9"


class TestNSS:
    def test_consultar_nss_sin_correo(self):
        """Falta correo → 422 (Pydantic valida)."""
        client = TestClient(app)
        response = client.post("/nss", json={"curp": "GALJ800101HDFRRNA9"})
        assert response.status_code == 422

    def test_consultar_nss_con_error(self):
        """Mock default → 500."""
        client = TestClient(app)
        response = client.post("/nss", json={
            "curp": "GALJ800101HDFRRNA9",
            "correo": "test@test.com",
        })
        assert response.status_code == 500

    @patch("src.api._get_solver")
    @patch("src.api.NSSModule")
    def test_consultar_nss_exitoso(self, mock_mod_cls, mock_solver):
        mock_solver.return_value = MagicMock()
        mock_instance = AsyncMock()
        mock_instance.consultar = AsyncMock(return_value={
            "nss": "12345678901",
            "curp": "GALJ800101HDFRRNA9",
        })
        mock_mod_cls.return_value = mock_instance

        client = TestClient(app)
        response = client.post("/nss", json={
            "curp": "GALJ800101HDFRRNA9",
            "correo": "test@test.com",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["nss"] == "12345678901"


# ── Rate limiting ──────────────────────────────────────────────────────────────

class TestRateLimiting:
    """Verifica que slowapi aplica 429 cuando se excede el límite."""

    def test_root_rate_limit_after_40_requests(self):
        """Endpoint / (30/min) debe dar 429 tras exceder el límite."""
        client = TestClient(app)
        statuses = {}
        for _ in range(45):
            response = client.get("/")
            statuses[response.status_code] = statuses.get(response.status_code, 0) + 1

        assert 200 in statuses, "Debe haber respuestas exitosas"
        assert 429 in statuses, "Debe rate-limitear después de 30 requests"
        assert statuses[200] >= 25, "Debe permitir ~30 requests antes de limitar"

    def test_health_rate_limit_independent(self):
        """/health tiene su propio contador (30/min) independiente de /."""
        client = TestClient(app)
        statuses = {}
        for _ in range(40):
            response = client.get("/health")
            statuses[response.status_code] = statuses.get(response.status_code, 0) + 1

        assert 200 in statuses
        assert 429 in statuses


class TestRateLimit:
    """Line 58-60: _rate_limit helper."""

    def test_rate_limit_from_env(self):
        with patch.dict(os.environ, {"RATE_LIMIT_TEST": "10/minute"}):
            from src.api import _rate_limit
            assert _rate_limit("TEST", "5/minute") == "10/minute"

    def test_rate_limit_default(self):
        from src.api import _rate_limit
        assert _rate_limit("NONEXISTENT", "5/minute") == "5/minute"


# ── _tramite_exception_to_http: mapeo de excepciones (109-123) ────────────────

class TestExceptionMapping:
    """_tramite_exception_to_http — mro + hints de validación."""

    def _map(self, exc):
        from src.api import _tramite_exception_to_http
        return _tramite_exception_to_http(exc)

    def test_captcha_maps_409(self):
        from src.exceptions import CaptchaError
        assert self._map(CaptchaError("x")).status_code == 409

    def test_ocr_maps_422(self):
        from src.exceptions import OCRError
        assert self._map(OCRError("x")).status_code == 422

    def test_mail_reader_maps_502(self):
        from src.exceptions import MailReaderError
        assert self._map(MailReaderError("x")).status_code == 502

    def test_voice_maps_422(self):
        from src.exceptions import VoiceInputError
        assert self._map(VoiceInputError("x")).status_code == 422

    def test_documento_maps_422(self):
        from src.exceptions import DocumentoError
        assert self._map(DocumentoError("x")).status_code == 422

    def test_claude_maps_502(self):
        from src.exceptions import ClaudeError
        assert self._map(ClaudeError("x")).status_code == 502

    def test_storage_maps_500(self):
        from src.exceptions import StorageError
        assert self._map(StorageError("x")).status_code == 500

    def test_tramite_generico_maps_500(self):
        from src.exceptions import TramiteError
        assert self._map(TramiteError("x")).status_code == 500

    def test_module_error_con_hint_maps_422(self):
        """ModuleError con hint de validación → 422 (119-121)."""
        from src.exceptions import ModuleError
        assert self._map(ModuleError("Se requiere CURP")).status_code == 422

    def test_module_error_sin_hint_maps_502(self):
        from src.exceptions import ModuleError
        assert self._map(ModuleError("el portal cayó")).status_code == 502


# ── _verify_api_key: auth middleware (143-160) ────────────────────────────────

class TestVerifyApiKey:
    """_verify_api_key — paths públicos, dev sin key, key inválida/válida."""

    async def _call(self, path, api_key, header_key=None):
        import src.api as api
        request = MagicMock()
        request.url.path = path
        request.headers.get = MagicMock(return_value=header_key)
        call_next = AsyncMock(return_value="RESP")
        with patch.object(api, "API_KEY", api_key), \
             patch.object(api, "_API_KEY_WARNED", False):
            result = await api._verify_api_key(request, call_next)
        return result, call_next

    def test_public_path_skips_auth(self):
        import asyncio
        result, call_next = asyncio.run(self._call("/health", "secret", None))
        assert result == "RESP"
        call_next.assert_awaited_once()

    def test_no_api_key_dev_mode_warns_once(self):
        import asyncio

        import src.api as api
        request = MagicMock()
        request.url.path = "/curp"
        call_next = AsyncMock(return_value="RESP")
        with patch.object(api, "API_KEY", ""), \
             patch.object(api, "_API_KEY_WARNED", False), \
             patch.object(api.logger, "warning") as mock_warn:
            asyncio.run(api._verify_api_key(request, call_next))
            asyncio.run(api._verify_api_key(request, call_next))
        assert mock_warn.call_count == 1  # warning solo 1 vez

    def test_key_invalida_403(self):
        import asyncio
        result, call_next = asyncio.run(self._call("/curp", "secret", "wrong"))
        assert result.status_code == 403
        call_next.assert_not_awaited()

    def test_key_valida_pasa(self):
        import asyncio
        result, call_next = asyncio.run(self._call("/curp", "secret", "secret"))
        assert result == "RESP"
        call_next.assert_awaited_once()


# ── Import-time branches de producción (134-135, 236-241, 255) ────────────────

class TestZProductionReload:
    """Ramas de import de api.py en modo producción — via importlib.reload.

    Recargar el módulo con PRODUCTION=1 cubre ramas que solo existen en
    deploy (API_KEY requerida, CORS explícito, middleware auth). Es la
    última clase del archivo: el reload deja el módulo en estado prod.
    """

    def test_prod_sin_api_key_exits(self):
        import importlib

        import src.api as api
        with patch.dict(os.environ, {"PRODUCTION": "1", "STORAGE_KEY": "x"}), \
             patch.dict(os.environ, {"API_KEY": ""}):
            with pytest.raises(SystemExit):
                importlib.reload(api)

    def test_prod_cors_sin_origins_raises(self):
        import importlib

        import src.api as api
        with patch.dict(os.environ, {
            "PRODUCTION": "1", "API_KEY": "k", "STORAGE_KEY": "x",
        }), patch.dict(os.environ, {"CORS_ORIGINS": ""}):
            with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
                importlib.reload(api)

    def test_prod_completo_middleware_y_solver(self):
        import importlib

        import src.api as api
        with patch("src.utils.captcha.CaptchaSolver") as mock_cs, \
             patch("src.utils.free_captcha.FreeCaptchaSolver") as mock_fc, \
             patch.dict(os.environ, {
                 "PRODUCTION": "1", "API_KEY": "k", "STORAGE_KEY": "x",
                 "CORS_ORIGINS": "https://a.com", "CAPTCHA_API_KEY": "real-key",
             }):
            api = importlib.reload(api)
            # middleware auth registrado (255)
            assert len(api.app.user_middleware) > 0
            # _get_solver: primera llamada construye, segunda usa cache (286-300)
            s1 = api._get_solver()
            assert api._get_solver() is s1  # 287 cache
            mock_cs.assert_called_once_with("real-key")
            # sin CAPTCHA_API_KEY → FreeCaptchaSolver (295-298)
            with patch.dict(os.environ, {"CAPTCHA_API_KEY": ""}):
                api._SOLVER_CACHE = None
                s2 = api._get_solver()
            assert s2 is mock_fc.return_value
            # CaptchaSolver lanza CaptchaError → fallback free (293-294)
            from src.exceptions import CaptchaError
            mock_cs.side_effect = CaptchaError("boom")
            with patch.dict(os.environ, {"CAPTCHA_API_KEY": "real-key"}):
                api._SOLVER_CACHE = None
                s3 = api._get_solver()
            assert s3 is mock_fc.return_value


# ── _get_solver cache (287) — verificado en TestZProductionReload ─────────────

class TestPerfilMinimo:
    """ProfileData con solo alias → validators None-path (205, 213)."""

    @patch("src.api.save_profile")
    def test_perfil_solo_alias(self, mock_save):
        client = TestClient(app)
        response = client.post("/perfiles", json={"alias": "anon"})
        assert response.status_code == 200
        assert response.json()["alias"] == "anon"

    def test_validator_curp_none_path(self):
        from src.api import ProfileData
        assert ProfileData.validate_curp(None) is None  # línea 205

    def test_validator_correo_none_path(self):
        from src.api import ProfileData
        assert ProfileData.validate_correo(None) is None  # línea 213


# ── Handlers: except TramiteError / StorageError (337-338, 356-357, 370-371, 382-383) ──

class TestExceptionHandlers:
    """Endpoints con excepciones de dominio → status code mapeado."""

    def test_curp_tramite_error_maps_409(self):
        from src.exceptions import CaptchaError
        with patch("src.api.CURPModule") as mock_cls:
            inst = AsyncMock()
            inst.consultar = AsyncMock(side_effect=CaptchaError("captcha no resuelto"))
            mock_cls.return_value = inst
            client = TestClient(app)
            response = client.post("/curp", json={"curp": "GALJ800101HDFRRNA9"})
        assert response.status_code == 409

    def test_nss_tramite_error_maps_502(self):
        from src.exceptions import ModuleError
        with patch("src.api.NSSModule") as mock_cls:
            inst = AsyncMock()
            inst.consultar = AsyncMock(side_effect=ModuleError("portal caído"))
            mock_cls.return_value = inst
            client = TestClient(app)
            response = client.post("/nss", json={
                "curp": "GALJ800101HDFRRNA9", "correo": "test@test.com",
            })
        assert response.status_code == 502

    def test_listar_perfiles_storage_error(self):
        from src.exceptions import StorageError
        with patch("src.api.list_profiles",
                   side_effect=StorageError("storage caído")):
            client = TestClient(app)
            response = client.get("/perfiles")
        assert response.status_code == 500

    def test_guardar_perfil_storage_error(self):
        from src.exceptions import StorageError
        with patch("src.api.save_profile",
                   side_effect=StorageError("storage caído")):
            client = TestClient(app)
            response = client.post("/perfiles", json={"alias": "x"})
        assert response.status_code == 500


# ── _get_solver cache (287) — verificado en TestZProductionReload ─────────────
