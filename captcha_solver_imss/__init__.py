"""
captcha_solver_imss — Solver para CAPTCHA de imagen del IMSS.
"""
from .solver import IMSCaptchaSolver
from .store import CaptchaStore

__all__ = ["IMSCaptchaSolver", "CaptchaStore"]
