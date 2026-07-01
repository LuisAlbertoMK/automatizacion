"""Shared fixtures for tramite module tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_page():
    """Mock Playwright page."""
    page = AsyncMock()
    page.content = AsyncMock(return_value="<html></html>")
    page.pdf = AsyncMock()
    page.url = "https://example.com"
    return page


@pytest.fixture
def mock_browser(mock_page):
    """Mock Playwright browser + context."""
    browser = AsyncMock()
    context = AsyncMock()
    context.new_page = AsyncMock(return_value=mock_page)
    browser.new_context = AsyncMock(return_value=context)
    return browser


@pytest.fixture
def mock_playwright(mock_browser):
    """Mock Playwright launch."""
    p = MagicMock()
    p.launch = AsyncMock(return_value=mock_browser)
    return p


@pytest.fixture
def base_mocks(mock_playwright, mock_browser, mock_page):
    """Tuple of (mock_playwright, mock_browser, mock_page)."""
    return mock_playwright, mock_browser, mock_page


def make_consultar_success(result: dict):
    """Helper: crea un _run AsyncMock que retorna un resultado exitoso."""
    return AsyncMock(return_value=result)
