"""
test.py
Modo de prueba para validar el solver con imágenes etiquetadas.

Uso:
    py -m captcha_solver_imss.test                              # probar carpeta test_samples/
    py -m captcha_solver_imss.test --dir captcha_solver_imss/capturas  # probar capturas guardadas
    py -m captcha_solver_imss.test --image ruta.png              # probar una imagen específica

Para etiquetar imágenes de prueba:
    1. Pone las imágenes en captcha_solver_imss/test_samples/
    2. El nombre debe ser: <valor_esperado>_<random>.png
       Ej: "A7FK3_01.png", "X9P2M_02.png", "VEG4GDM_03.png"
    3. Ejecutá este script y te dice cuáles acertó y cuáles no
"""

import sys
import argparse
from pathlib import Path


def test_single(solver, img_path: Path) -> dict:
    """Prueba el solver con una imagen y retorna resultado."""
    result = solver.solve_from_path(str(img_path))
    return result


def test_batch(solver, img_dir: Path, verbose: bool = True):
    """
    Prueba todas las imágenes en un directorio.
    
    Las imágenes deben nombrarse como: <VALOR_ESPERADO>_<cualquier_cosa>.png
    Ej: "A7FK3_01.png", "X9P2M_cualquier_nombre.png"
    """
    images = list(img_dir.glob("*.png")) + list(img_dir.glob("*.jpg"))
    
    if not images:
        print(f"  No se encontraron imágenes en {img_dir}")
        return

    total = len(images)
    correct = 0
    wrong = 0
    errors = 0
    details = []

    for img_path in sorted(images):
        # Extraer valor esperado del nombre del archivo
        expected = img_path.stem.split("_")[0].upper()

        result = test_single(solver, img_path)
        got = result.get("value", "")
        ok = result.get("success", False)

        # Comparación case-insensitive (solver normaliza a uppercase)
        if ok and got.upper() == expected.upper():
            correct += 1
            status = "OK"
        elif ok:
            wrong += 1
            status = "MAL"
        else:
            errors += 1
            status = "ERR"

        details.append({
            "file": img_path.name,
            "expected": expected,
            "got": got,
            "score": result.get("score", 0),
            "engine": result.get("engine", ""),
            "elapsed_ms": result.get("elapsed_ms", 0),
            "status": status,
        })

        if verbose:
            print(f"  {status} {img_path.name:30s}"
                  f"  esperado={expected:8s}  obtenido={got:8s}"
                  f"  score={result.get('score',0):.2f}"
                  f"  ({result.get('engine','')})")

    # Resumen
    rate = (correct / total) * 100 if total > 0 else 0
    print(f"\n  {'='*50}")
    print(f"  RESULTADOS: {correct}/{total} correctos ({rate:.1f}%)")
    print(f"  {'='*50}")
    print(f"  [OK] Correctos: {correct}")
    print(f"  [MAL] Incorrectos: {wrong}")
    print(f"  [ERR] Errores: {errors}")
    print()

    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "errors": errors,
        "rate": rate,
        "details": details,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Test del CaptchaSolver IMSS"
    )
    parser.add_argument("--dir", default="",
                        help="Directorio con imágenes de prueba")
    parser.add_argument("--image", default="",
                        help="Imagen específica para probar")
    parser.add_argument("--verbose", action="store_true", default=True,
                        help="Output detallado")
    
    args = parser.parse_args()

    from .solver import IMSCaptchaSolver
    solver = IMSCaptchaSolver(verbose=True)

    if args.image:
        # Probar imagen específica
        img = Path(args.image)
        if not img.exists():
            print(f"  Error: no existe {img}")
            sys.exit(1)
        result = test_single(solver, img)
        print(f"\n  Resultado: {result}")
        return

    # Probar directorio
    test_dir = Path(args.dir) if args.dir else (
        Path(__file__).parent / "test_samples"
    )
    test_batch(solver, test_dir, verbose=args.verbose)


if __name__ == "__main__":
    main()
