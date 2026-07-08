"""Tests para src/api.py — API REST FastAPI con TestClient."""

import os
import sys
from pathlib import Path
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
            "curp": "TEST123456",
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
        response = client.post("/curp", json={"curp": "GALJ800101HDFXXXX0"})
        assert response.status_code == 500

    @patch("src.api._get_solver")
    @patch("src.api.CURPModule")
    def test_consultar_curp_exitoso(self, mock_mod_cls, mock_solver):
        mock_solver.return_value = MagicMock()
        mock_instance = AsyncMock()
        mock_instance.consultar = AsyncMock(return_value={
            "curp": "GALJ800101HDFXXXX0",
            "nombre": "JUAN",
        })
        mock_mod_cls.return_value = mock_instance

        client = TestClient(app)
        response = client.post("/curp", json={"curp": "GALJ800101HDFXXXX0"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["curp"] == "GALJ800101HDFXXXX0"


class TestNSS:
    def test_consultar_nss_sin_correo(self):
        """Falta correo → 422 (Pydantic valida)."""
        client = TestClient(app)
        response = client.post("/nss", json={"curp": "GALJ800101HDFXXXX0"})
        assert response.status_code == 422

    def test_consultar_nss_con_error(self):
        """Mock default → 500."""
        client = TestClient(app)
        response = client.post("/nss", json={
            "curp": "GALJ800101HDFXXXX0",
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
            "curp": "GALJ800101HDFXXXX0",
        })
        mock_mod_cls.return_value = mock_instance

        client = TestClient(app)
        response = client.post("/nss", json={
            "curp": "GALJ800101HDFXXXX0",
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
