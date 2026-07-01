"""
modules/buro.py — BuroModule alias para compatibilidad.
Usar directamente: from modules.credito import CreditoModule
"""

from modules.credito import CreditoModule


class BuroModule(CreditoModule):
    """Wrapper de compatibilidad para BuroModule → CreditoModule(tipo='buro')."""

    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(tipo="buro", captcha_solver=captcha_solver, use_ocr=use_ocr)
