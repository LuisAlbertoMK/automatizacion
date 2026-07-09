"""Tests para src/utils/claude.py — mockeando httpx.Client."""

import json
import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.utils.claude import ClaudeError, call_claude


@pytest.fixture(autouse=True)
def setup_key():
    """Asegura ANTHROPIC_API_KEY para tests que lo necesitan."""
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key-12345"
    yield
    os.environ.pop("ANTHROPIC_API_KEY", None)


@pytest.fixture
def mock_client():
    """Mock de httpx.Client que devuelve un contexto manejable."""
    with patch("src.utils.claude.httpx.Client") as mc:
        instance = MagicMock()
        mc.return_value.__enter__.return_value = instance
        yield instance


def _ok_response(text: str) -> dict:
    """Construye respuesta mock para status 200."""
    return {
        "status_code": 200,
        "json.return_value": {"content": [{"text": text}]},
    }


class TestCallClaude:
    def test_returns_parsed_json(self, mock_client):
        """Llamada exitosa → JSON parseado."""
        mock_client.post.return_value = MagicMock(**_ok_response(
            '{"resultado": "ok"}'
        ))

        result = call_claude([{"role": "user", "content": "test"}])
        assert result == {"resultado": "ok"}

    def test_passes_correct_payload(self, mock_client):
        """Verifica URL, headers, payload que se envía."""
        mock_client.post.return_value = MagicMock(**_ok_response(
            '{"ok": true}'
        ))

        call_claude([{"role": "user", "content": "Hola"}], max_tokens=500, model="claude-sonnet-4")

        mock_client.post.assert_called_once()
        args, kwargs = mock_client.post.call_args
        assert args[0] == "https://api.anthropic.com/v1/messages"
        assert kwargs["json"]["model"] == "claude-sonnet-4"
        assert kwargs["json"]["max_tokens"] == 500
        assert kwargs["headers"]["x-api-key"] == "sk-ant-test-key-12345"
        assert kwargs["headers"]["anthropic-version"] == "2023-06-01"

    def test_strips_markdown_backticks(self, mock_client):
        """Limpia ```json y ``` del texto antes de parsear."""
        mock_client.post.return_value = MagicMock(**_ok_response(
            "```json\n{\"key\": \"value\"}\n```"
        ))

        result = call_claude([{"role": "user", "content": "test"}])
        assert result == {"key": "value"}

    def test_raises_on_missing_api_key(self):
        """Sin ANTHROPIC_API_KEY → ClaudeError."""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with pytest.raises(ClaudeError, match="ANTHROPIC_API_KEY no configurada"):
            call_claude([])

    def test_raises_on_invalid_api_key_prefix(self):
        """Key que no empieza con sk-ant- → ClaudeError."""
        os.environ["ANTHROPIC_API_KEY"] = "invalid-key"
        with pytest.raises(ClaudeError, match="ANTHROPIC_API_KEY no configurada"):
            call_claude([])

    def test_raises_on_timeout(self, mock_client):
        """httpx.TimeoutException → ClaudeError."""
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        with pytest.raises(ClaudeError, match="Timeout"):
            call_claude([{"role": "user", "content": "test"}])

    def test_raises_on_connection_error(self, mock_client):
        """httpx.RequestError → ClaudeError."""
        mock_client.post.side_effect = httpx.RequestError("connection failed")
        with pytest.raises(ClaudeError, match="Error de conexión"):
            call_claude([{"role": "user", "content": "test"}])

    def test_raises_on_http_error(self, mock_client):
        """Status code no 200 → ClaudeError con cuerpo."""
        mock_client.post.return_value = MagicMock(
            status_code=400,
            text='{"error": "bad request"}',
            reason_phrase="Bad Request",
        )

        with pytest.raises(ClaudeError, match="Anthropic API error 400"):
            call_claude([{"role": "user", "content": "test"}])

    def test_raises_on_empty_content(self, mock_client):
        """Respuesta sin content → ClaudeError."""
        mock_client.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"content": []},
        )

        with pytest.raises(ClaudeError, match="Respuesta inesperada"):
            call_claude([{"role": "user", "content": "test"}])

    def test_raises_on_invalid_json_in_response(self, mock_client):
        """Si el texto de Claude no es JSON válido → ClaudeError."""
        mock_client.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"content": [{"text": "esto no es json"}]},
        )

        with pytest.raises(ClaudeError, match="Claude no devolvió JSON válido"):
            call_claude([{"role": "user", "content": "test"}])
