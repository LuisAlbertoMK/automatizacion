"""
test_captcha_solver.py
Prueba rápida del IMSCaptchaSolver con imágenes existentes.

Uso:
    py test_captcha_solver.py                          # prueba debug_captcha_imss.png
    py test_captcha_solver.py ruta/de/mi/captcha.png   # prueba imagen específica
    py test_captcha_solver.py --store                  # guarda en store
"""

import sys
from pathlib import Path

from captcha_solver_imss import CaptchaStore, IMSCaptchaSolver


def main():
    # Determinar imagen a procesar
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        img_path = Path(sys.argv[1])
    else:
        img_path = Path("debug_captcha_imss.png")
        if not img_path.exists():
            img_path = Path("captcha_imss_actual.png")

    if not img_path.exists():
        print(f"No se encontró imagen en {img_path}")
        print("Pasá una ruta como argumento o guardá una en debug_captcha_imss.png")
        sys.exit(1)

    print(f"Procesando: {img_path.name} ({img_path.stat().st_size} bytes)")

    # Solver con store opcional
    use_store = "--store" in sys.argv
    store = CaptchaStore() if use_store else None

    solver = IMSCaptchaSolver(store=store, verbose=True)
    result = solver.solve_from_path(str(img_path))

    print(f"\n{'='*50}")
    print("RESULTADO:")
    print(f"  success:   {result['success']}")
    print(f"  value:     '{result['value']}'")
    print(f"  engine:    {result['engine']}")
    print(f"  score:     {result['score']}")
    print(f"  elapsed:   {result['elapsed_ms']}ms")
    print(f"  variants:  {result['variants_tried']}")
    if result.get("error"):
        print(f"  error:     {result['error']}")
    print(f"{'='*50}")

    if use_store:
        stats = store.stats()
        print(f"\nStore stats: {stats}")


if __name__ == "__main__":
    main()
