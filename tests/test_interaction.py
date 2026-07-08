"""Tests unitarios para utils/interaction.py — InteractionHandler."""

from unittest.mock import patch

import pytest

from src.utils.interaction import (CLIPromptHandler, InteractionHandler,
                                   TimedPromptHandler)


class TestInteractionHandler:
    """ABC — verifica que no se puede instanciar directamente."""

    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError, match="abstract"):
            InteractionHandler()


class TestCLIPromptHandler:
    """CLIPromptHandler — usa input() real (mockeado)."""

    @patch("builtins.input", return_value="texto ingresado")
    @pytest.mark.asyncio
    async def test_prompt_returns_stripped(self, mock_input):
        handler = CLIPromptHandler()
        result = await handler.prompt("Ingresá algo:")
        assert result == "texto ingresado"

    @patch("builtins.input", return_value="  con espacios  ")
    @pytest.mark.asyncio
    async def test_prompt_strips_spaces(self, mock_input):
        handler = CLIPromptHandler()
        result = await handler.prompt("Test:")
        assert result == "con espacios"  # strip aplicado

    @patch("builtins.input", return_value="")
    @pytest.mark.asyncio
    async def test_prompt_enter_no_return(self, mock_input):
        """prompt_enter no retorna valor."""
        handler = CLIPromptHandler()
        result = await handler.prompt_enter("Presioná Enter:")
        assert result is None

    @patch("builtins.input", return_value="  ")
    @pytest.mark.asyncio
    async def test_prompt_blank_input(self, mock_input):
        """input vacío o espacios retorna string vacío."""
        handler = CLIPromptHandler()
        result = await handler.prompt("Ingresá algo:")
        assert result == ""

    @pytest.mark.asyncio
    async def test_prompt_message_displayed(self):
        """Verifica que el mensaje se pase a input()."""
        handler = CLIPromptHandler()
        with patch("builtins.input", return_value="ok") as mock_input:
            await handler.prompt("Test message:")
            mock_input.assert_called_once_with("  Test message:")

    @pytest.mark.asyncio
    async def test_prompt_enter_message_displayed(self):
        """prompt_enter también muestra el mensaje."""
        handler = CLIPromptHandler()
        with patch("builtins.input", return_value="") as mock_input:
            await handler.prompt_enter("Presione Enter:")
            mock_input.assert_called_once_with("  Presione Enter:")


class TestTimedPromptHandler:
    """TimedPromptHandler — siempre levanta TimeoutError."""

    @pytest.mark.asyncio
    async def test_prompt_raises_timeout(self):
        handler = TimedPromptHandler(timeout=30.0)
        with pytest.raises(TimeoutError, match="Se requiere interacción"):
            await handler.prompt("Ingresá algo:")

    @pytest.mark.asyncio
    async def test_prompt_enter_raises_timeout(self):
        handler = TimedPromptHandler(timeout=10.0)
        with pytest.raises(TimeoutError, match="Se requiere interacción"):
            await handler.prompt_enter("Presione Enter:")

    def test_default_timeout(self):
        handler = TimedPromptHandler()
        assert handler.timeout == 30.0

    def test_custom_timeout(self):
        handler = TimedPromptHandler(timeout=5.0)
        assert handler.timeout == 5.0
