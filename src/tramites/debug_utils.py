"""Helpers de debug para trámites (inputs visibles + screenshots).

Extraídos de src/tramites/base.py (incremento 2). `find_visible_inputs`
es puro (solo usa `page`); `take_debug_screenshot` respeta el gate
HEADLESS/VERBOSE que recibe por parámetros explícitos.
"""


async def find_visible_inputs(page, keyword: str = "") -> list:
    """Lista inputs visibles para debug. Si keyword, busca coincidencia."""
    inputs = await page.query_selector_all("input[type='text'], input:not([type])")
    found = []
    for inp in inputs:
        if await inp.is_visible():
            name = await inp.get_attribute("name") or ""
            id_attr = await inp.get_attribute("id") or ""
            placeholder = await inp.get_attribute("placeholder") or ""
            if not keyword or keyword.lower() in (name + id_attr + placeholder).lower():
                found.append({"element": inp, "name": name, "id": id_attr, "placeholder": placeholder})
    return found


async def take_debug_screenshot(page, path: str = "debug.png",
                               headless: bool = True, verbose: bool = False,
                               on_debug=None):
    """Toma screenshot para debug (solo si not headless o verbose)."""
    if not headless or verbose:
        try:
            await page.screenshot(path=path)
            if on_debug is not None:
                on_debug(f"Screenshot: {path}")
        except Exception:
            if on_debug is not None:
                on_debug("Error tomando screenshot de debug")
