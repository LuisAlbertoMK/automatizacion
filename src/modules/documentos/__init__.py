"""
modules/documentos/ — Generación de documentos con IA.
Migrado de tramites-auto/tramites-bot/docs/.
"""

from .cv import CVGenerator
from .escrito import EscritoGenerator

__all__ = ["CVGenerator", "EscritoGenerator"]
