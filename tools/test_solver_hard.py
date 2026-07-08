"""
Debug: test only the 5 images that fail.
"""
from pathlib import Path

from captcha_solver_imss import IMSCaptchaSolver

solver = IMSCaptchaSolver(verbose=True)

hard_cases = [
    'u42v6pR.PNG',
    '5TRrJTb.PNG',
    'RnqqfTX.PNG',
    'XbHH58B.PNG',
    'XUUruEU.PNG',
]

for fname in hard_cases:
    img = Path('D:/automatizacion/ejemplos_captchas') / fname
    result = solver.solve_from_path(str(img))
    print(f"\n>>> {fname} -> '{result['value']}' (score={result['score']:.2f})")
    print()
