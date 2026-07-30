"""
verify_portals.py
Verifica que los portales gob.mx estén accesibles y su estructura HTML sea la esperada.

Uso:
    py -m tools.verify_portals
    py tools/verify_portals.py --portal curp
    py tools/verify_portals.py --portal nss
    py tools/verify_portals.py --portal all

No hace consultas reales — solo verifica:
  1. Que el portal responda HTTP 200
  2. Que el formulario principal esté presente
  3. Que los campos esperados existan
"""
import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


PORTALS = {
    "curp": {
        "name": "CURP (RENAPO)",
        "url": "https://www.gob.mx/curp/",
        "selectors": {
            "form": "form",
            "curp_input": "input[name*='curp'], input[id*='curp'], #curp, input[placeholder*='CURP']",
            "search_button": "button[type='submit'], input[type='submit'], button:has-text('Buscar')",
        },
    },
    "nss": {
        "name": "NSS (IMSS)",
        "url": "https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asignacionNSS",
        "selectors": {
            "form": "form",
            "curp_input": "input[name*='curp'], input[id*='curp'], #curp",
            "email_input": "input[type='email'], input[name*='correo'], input[name*='email']",
        },
    },
    "rfc": {
        "name": "RFC (SAT)",
        "url": "https://www.sat.gob.mx/tramites/operacion/28753/",
        "selectors": {
            "form": "form",
        },
    },
    "acta_nacimiento": {
        "name": "Acta de Nacimiento",
        "url": "https://www.gob.mx/actas",
        "selectors": {
            "form": "form",
        },
    },
    "pasaporte": {
        "name": "Pasaporte (SRE)",
        "url": "https://www.gob.mx/tramites/ficha/pasaporte-para-adultos/SRE230",
        "selectors": {
            "form": "form",
        },
    },
    "control_confianza": {
        "name": "Control de Confianza",
        "url": "https://certificado.sesnsp.gob.mx/",
        "selectors": {
            "form": "form",
        },
    },
    "antecedentes": {
        "name": "Antecedentes No Penales",
        "url": "https://constancias.oadprs.gob.mx/",
        "selectors": {
            "form": "form",
        },
    },
    "semanas": {
        "name": "Semanas Cotizadas (IMSS)",
        "url": "https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asegurado",
        "selectors": {
            "form": "form",
        },
    },
    "cita_ine": {
        "name": "Cita INE",
        "url": "https://www.ine.mx/credencial/citas/",
        "selectors": {
            "form": "form",
        },
    },
    "cita_sat": {
        "name": "Cita SAT",
        "url": "https://citas.sat.gob.mx/",
        "selectors": {
            "form": "form",
        },
    },
    "tenencia": {
        "name": "Tenencia EdoMex",
        "url": "https://sfpya.edomexico.gob.mx/",
        "selectors": {
            "form": "form",
        },
    },
}


async def verify_portal(portal_key: str, headless: bool = True) -> dict:
    """Verifica un portal específico contra el portal real."""
    from playwright.async_api import async_playwright

    portal = PORTALS[portal_key]
    result = {
        "portal": portal["name"],
        "url": portal["url"],
        "reachable": False,
        "http_status": None,
        "load_time_ms": 0,
        "form_found": False,
        "inputs_found": [],
        "errors": [],
    }

    try:
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
                viewport={"width": 1280, "height": 720},
            )
            page = await context.new_page()

            start = time.time()
            try:
                response = await page.goto(
                    portal["url"],
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                result["http_status"] = response.status if response else None
                result["reachable"] = response.ok if response else False
            except Exception as e:
                result["errors"].append(f"Navigation error: {e}")
                await browser.close()
                return result

            result["load_time_ms"] = int((time.time() - start) * 1000)

            # Check form
            form_sel = portal["selectors"].get("form", "form")
            forms = await page.locator(form_sel).count()
            result["form_found"] = forms > 0

            # Check each expected input
            for input_name, input_sel in portal["selectors"].items():
                if input_name == "form":
                    continue
                try:
                    count = await page.locator(input_sel).count()
                    result["inputs_found"].append({
                        "name": input_name,
                        "selector": input_sel,
                        "found": count > 0,
                        "count": count,
                    })
                except Exception as e:
                    result["inputs_found"].append({
                        "name": input_name,
                        "selector": input_sel,
                        "found": False,
                        "error": str(e),
                    })

            await browser.close()

    except Exception as e:
        result["errors"].append(f"Unexpected error: {e}")

    return result


def print_result(result: dict):
    """Pretty-print verification result."""
    status = "✅ OK" if result["reachable"] else "❌ FAIL"
    print(f"\n{'='*60}")
    print(f"  {result['portal']}")
    print(f"  URL: {result['url']}")
    print(f"  Status: {status} (HTTP {result['http_status']})")
    print(f"  Load time: {result['load_time_ms']}ms")
    print(f"  Form found: {'✅' if result['form_found'] else '❌'}")

    for inp in result["inputs_found"]:
        icon = "✅" if inp.get("found") else "❌"
        print(f"    {icon} {inp['name']}: {inp['selector']}")

    if result["errors"]:
        print("  Errors:")
        for e in result["errors"]:
            print(f"    ⚠️  {e}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Verify gob.mx portals")
    parser.add_argument("--portal", default="all", choices=["curp", "nss", "all"])
    parser.add_argument("--show-browser", action="store_true",
                        help="Show browser window (non-headless)")
    args = parser.parse_args()

    portals = list(PORTALS.keys()) if args.portal == "all" else [args.portal]
    headless = not args.show_browser

    print("🔍 Verificando portales gob.mx...")
    print(f"  Modo: {'headless' if headless else 'visible'}")

    results = []
    for key in portals:
        print(f"\n  Consultando {PORTALS[key]['name']}...")
        result = await verify_portal(key, headless=headless)
        results.append(result)
        print_result(result)

    # Summary
    print(f"\n{'='*60}")
    print("  RESUMEN:")
    for r in results:
        status = "✅" if r["reachable"] and r["form_found"] else "❌"
        print(f"  {status} {r['portal']}: HTTP {r['http_status']}, "
              f"form={'OK' if r['form_found'] else 'MISSING'}, "
              f"{r['load_time_ms']}ms")


if __name__ == "__main__":
    asyncio.run(main())
