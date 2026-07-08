"""
utils/interaction.py
Handler de interacción con el usuario — abstrae input() bloqueante.

Permite que módulos async funcionen tanto en CLI (input()) como en
API (TimeoutPrompt) sin cambiar el código del módulo.
"""
from abc import ABC, abstractmethod


class InteractionHandler(ABC):
    """Handler abstracto de interacción con el usuario."""

    @abstractmethod
    async def prompt(self, message: str) -> str:
        """Pide al usuario que ingrese texto."""

    async def prompt_enter(self, message: str) -> None:
        """Espera a que el usuario presione Enter."""
        await self.prompt(message)


class CLIPromptHandler(InteractionHandler):
    """Handler por defecto — usa input() estándar."""

    async def prompt(self, message: str) -> str:
        return input(f"  {message}").strip()

    async def prompt_enter(self, message: str) -> None:
        input(f"  {message}")


class TimedPromptHandler(InteractionHandler):
    """Handler con timeout — para APIs.
    
    Si no hay respuesta en `timeout` segundos, levanta TimeoutError.
    """
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def prompt(self, message: str) -> str:
        raise TimeoutError(
            f"Se requiere interacción del usuario pero no hay CLI disponible "
            f"(timeout={self.timeout}s): {message}"
        )

    async def prompt_enter(self, message: str) -> None:
        raise TimeoutError(
            f"Se requiere interacción del usuario pero no hay CLI disponible "
            f"(timeout={self.timeout}s): {message}"
        )
