"""Test de generación de documentos (sin Claude API)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

# 1. Importan bien
from modules.documentos.cv import CVGenerator
from modules.documentos.escrito import EscritoGenerator
from utils.claude import ClaudeError

print("[OK] Imports")

# 2. CV .docx con datos hardcodeados
g = CVGenerator()
cv_data = {
    "nombre_completo": "Juan Pérez García",
    "titulo_profesional": "Ingeniero de Software",
    "resumen": "Profesional con 10 años de experiencia en desarrollo.",
    "experiencia": [{"empresa": "TechCo", "puesto": "Sr Dev", "periodo": "2020-2024", "logros": ["Lideró equipo de 5 personas"]}],
    "educacion": [{"institucion": "UNAM", "grado": "Ing. Computación", "año": "2014"}],
    "habilidades": ["Python", "Node.js", "Docker"],
    "idiomas": ["Español nativo", "Inglés C1"],
    "contacto": {"telefono": "5512345678", "email": "juan@test.com", "ciudad": "CDMX"},
}
doc = g._construir_docx(cv_data)
out = Path("output/test_cv.docx")
doc.save(str(out))
print(f"[OK] CV .docx generado: {out.stat().st_size} bytes")

# 3. Escrito .docx
eg = EscritoGenerator()
escrito_data = {
    "titulo": "Carta de Presentación",
    "lugar_fecha": "CDMX, 25 de junio de 2026",
    "destinatario": "Empresa XYZ S.A. de C.V.",
    "asunto": "Solicitud de empleo",
    "cuerpo": ["Por medio de la presente me permito presentar mi solicitud...", "Agradezco la atención."],
    "cierre": "Atentamente",
    "firmante": "Juan Pérez García",
    "notas_legales": "",
}
doc2 = eg._construir_docx(escrito_data)
out2 = Path("output/test_escrito.docx")
doc2.save(str(out2))
print(f"[OK] Escrito .docx generado: {out2.stat().st_size} bytes")

# 4. ClaudeError funciona
try:
    raise ClaudeError("test error")
except ClaudeError:
    pass
print("[OK] ClaudeError")

print("\n✅ Todos los tests de documentos OK")
