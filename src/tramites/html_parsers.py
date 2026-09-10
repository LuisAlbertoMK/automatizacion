"""Helpers puros de parsing HTML para trámites.

Extraídos de src/tramites/base.py (incremento 1): funciones sin estado
que extraen CURP/NSS desde HTML crudo. Sin dependencias de Playwright.
"""

import re


def extract_curp_from_html(html: str) -> str | None:
    match = re.search(r"\b([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b", html)
    return match.group(1) if match else None


def extract_nss_from_html(html: str) -> str | None:
    match = re.search(r"\b(\d{11})\b", html)
    return match.group(1) if match else None
