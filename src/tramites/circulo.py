"""
modules/circulo.py — CirculoModule alias para compatibilidad.
Usar directamente: from src.tramites.credito import CreditoModule
"""

from src.tramites.credito import CreditoModule


class CirculoModule(CreditoModule):
    """Wrapper de compatibilidad para CirculoModule → CreditoModule(tipo='circulo')."""

    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(tipo="circulo", captcha_solver=captcha_solver, use_ocr=use_ocr)
