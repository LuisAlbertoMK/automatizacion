"""
utils/claude.py — Cliente Anthropic Claude API.

Migrado de tramites-auto/utils/helpers.js → llamarClaudeAPI().
Usa fetch nativo (httpx) sin SDK para mantener bajo perfil de dependencias.

Uso:
    result = call_claude([{"role": "user", "content": "Hola"}], max_tokens=2000)
"""

import json
import os

import httpx

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_TIMEOUT = 60  # segundos
DEFAULT_MAX_TOKENS = 2000


class ClaudeError(Exception):
    """Error en llamada a Anthropic Claude API."""
    pass


def call_claude(
    messages: list[dict],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """
    Llama a Claude API y devuelve el JSON parseado de la respuesta.

    Args:
        messages: Lista de mensajes estilo Anthropic [{"role": "user", "content": "..."}]
        max_tokens: Máximo de tokens en la respuesta
        model: Modelo a usar
        timeout: Timeout en segundos

    Returns:
        dict con el JSON parseado de la respuesta

    Raises:
        ClaudeError: Si hay error de API, timeout, o parseo
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or not api_key.startswith("sk-ant-"):
        raise ClaudeError(
            "ANTHROPIC_API_KEY no configurada o inválida.\n"
            "  1. Configurá ANTHROPIC_API_KEY en config.env o Windows Credential Manager\n"
            "  2. Obtené tu API key en https://console.anthropic.com"
        )

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise ClaudeError(f"Timeout tras {timeout}s llamando a Claude API")
    except httpx.RequestError as e:
        raise ClaudeError(f"Error de conexión con Claude API: {e}")

    if resp.status_code != 200:
        body = resp.text[:500] if resp.text else resp.reason_phrase
        raise ClaudeError(f"Anthropic API error {resp.status_code}: {body}")

    data = resp.json()
    if not data.get("content") or not data["content"][0].get("text"):
        raise ClaudeError("Respuesta inesperada de la API de Claude")

    texto = data["content"][0]["text"]
    # Limpiar posibles backticks markdown
    texto_limpio = texto.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(texto_limpio)
    except json.JSONDecodeError:
        raise ClaudeError(
            f"Claude no devolvió JSON válido:\n{texto_limpio[:300]}"
        )
