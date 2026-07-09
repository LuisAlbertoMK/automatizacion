"""Configuración global de tests — baja rondas bcrypt + mocks Playwright."""
import os
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.tramites.base import BaseModule, BrowserResources

# Reducir rondas bcrypt.kdf para tests (evita timeouts)
os.environ.setdefault("BCRYPT_KDF_ROUNDS", "16")
os.environ.setdefault("BCRYPT_HASH_ROUNDS", "8")


@pytest.fixture
def mock_page():
    """Mock de playwright Page — todos los métodos async son AsyncMock."""
    page = MagicMock()
    page.content = AsyncMock(return_value="<html><body>test</body></html>")
    page.wait_for_timeout = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.goto = AsyncMock()
    page.locator = MagicMock()
    page.evaluate = AsyncMock(return_value="")
    page.url = "https://example.com"
    # Métodos adicionales para módulos más complejos
    page.wait_for_selector = AsyncMock()
    page.query_selector = AsyncMock(return_value=None)
    page.select_option = AsyncMock()
    page.screenshot = AsyncMock()
    page.click = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.get_by_role = MagicMock()  # return_value configurable
    page.inner_text = AsyncMock(return_value="")
    return page


@pytest.fixture
def mock_br(mock_page):
    """Mock de BrowserResources con page mockeada."""
    br = MagicMock(spec=BrowserResources)
    br.page = mock_page
    br.close = AsyncMock()
    return br


@pytest.fixture
def mock_base(mock_br, request):
    """Parchea BaseModule para tests de módulos con Playwright.
    
    Devuelve un dict con referencias a los mocks para assertions.
    
    Uso:
        def test_foo(mock_base):
            mock_base['fill_field'].return_value = False
            mod = MiModulo()
            await mod.consultar(...)
            mock_base['goto'].assert_called_once()
    """
    mocks = {
        'br': mock_br,
        'page': mock_br.page,
        'goto': AsyncMock(),
        'fill_field': AsyncMock(return_value=True),
        'click_first': AsyncMock(return_value=True),
        'resolve_image_captcha': AsyncMock(return_value=True),
        'detect_site_key': AsyncMock(return_value=None),
        'wait_for_recaptcha': AsyncMock(return_value=True),
        'download_pdf': AsyncMock(return_value=Path("test.pdf")),
        'log': MagicMock(),
        'warn': MagicMock(),
        'error': MagicMock(),
        'debug': MagicMock(),
        'inject_recaptcha_token': AsyncMock(),
        'debug_screenshot': AsyncMock(),
        'find_visible_inputs': AsyncMock(return_value=[]),
    }

    @asynccontextmanager
    async def fake_browser_context(self):
        yield mock_br

    # Usar monkeypatch vía pytest internals — aplica y revuelve al yield
    import _pytest.monkeypatch
    mp = _pytest.monkeypatch.MonkeyPatch()

    mp.setattr(BaseModule, 'browser_context', fake_browser_context)
    mp.setattr(BaseModule, 'goto', mocks['goto'])
    mp.setattr(BaseModule, 'fill_field', mocks['fill_field'])
    mp.setattr(BaseModule, 'click_first', mocks['click_first'])
    mp.setattr(BaseModule, 'resolve_image_captcha', mocks['resolve_image_captcha'])
    mp.setattr(BaseModule, 'detect_site_key', mocks['detect_site_key'])
    mp.setattr(BaseModule, 'wait_for_recaptcha', mocks['wait_for_recaptcha'])
    mp.setattr(BaseModule, 'download_pdf', mocks['download_pdf'])
    mp.setattr(BaseModule, 'log', mocks['log'])
    mp.setattr(BaseModule, 'warn', mocks['warn'])
    mp.setattr(BaseModule, 'error', mocks['error'])
    mp.setattr(BaseModule, 'debug', mocks['debug'])
    mp.setattr(BaseModule, 'inject_recaptcha_token', mocks['inject_recaptcha_token'])
    mp.setattr(BaseModule, 'debug_screenshot', mocks['debug_screenshot'])
    mp.setattr(BaseModule, 'find_visible_inputs', mocks['find_visible_inputs'])

    yield mocks

    mp.undo()
