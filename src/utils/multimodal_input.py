"""
utils/multimodal_input.py
Interfaz unificada para entrada multimodal (texto, voz, imagen)

Funcionalidades:
  - Entrada de datos por texto, voz o imagen
  - Validación automática de formatos
  - Extracción inteligente de datos
  - Interfaz simple y consistente
"""

import os
import re
from typing import Literal

try:
    from src.utils.voice_input import WHISPER_AVAILABLE, VoiceInput, VoiceInputError
except ImportError:
    WHISPER_AVAILABLE = False

try:
    from src.utils.ocr import OCR_AVAILABLE, OCRError, OCRExtractor
except ImportError:
    OCR_AVAILABLE = False


InputMode = Literal["text", "voice", "image", "auto"]


class MultimodalInput:
    """Interfaz unificada para entrada multimodal."""

    def __init__(self, voice_model="base"):
        """
        Inicializa el sistema de entrada multimodal.
        
        Args:
            voice_model: Modelo de Whisper para voz ("tiny", "base", "small")
        """
        self.voice = None
        self.ocr = None

        # Inicializar voz si está disponible
        if WHISPER_AVAILABLE:
            try:
                self.voice = VoiceInput(model_size=voice_model)
                print("  [MULTIMODAL] [OK] Entrada por voz disponible")
            except Exception as e:
                print(f"  [MULTIMODAL] [!] Voz no disponible: {e}")
        else:
            print("  [MULTIMODAL] [!] Voz no disponible (instala: pip install openai-whisper sounddevice soundfile)")

        # Inicializar OCR si está disponible
        if OCR_AVAILABLE:
            try:
                self.ocr = OCRExtractor()
                print("  [MULTIMODAL] [OK] Entrada por imagen disponible")
            except Exception as e:
                print(f"  [MULTIMODAL] [!] OCR no disponible: {e}")
        else:
            print("  [MULTIMODAL] [!] OCR no disponible (instala Tesseract)")

    def get_curp(self, mode: InputMode = "text", prompt: str = "CURP") -> str:
        """
        Obtiene CURP por el modo especificado.
        
        Args:
            mode: "text", "voice", "image", "auto"
            prompt: Mensaje para el usuario
        
        Returns:
            CURP válida
        """
        if mode == "auto":
            mode = self._select_mode()

        if mode == "text":
            return self._get_curp_text(prompt)
        elif mode == "voice":
            return self._get_curp_voice()
        elif mode == "image":
            return self._get_curp_image()
        else:
            raise ValueError(f"Modo inválido: {mode}")

    def get_email(self, mode: InputMode = "text", prompt: str = "Correo electrónico") -> str:
        """
        Obtiene email por el modo especificado.
        
        Args:
            mode: "text", "voice", "image", "auto"
            prompt: Mensaje para el usuario
        
        Returns:
            Email válido
        """
        if mode == "auto":
            mode = self._select_mode()

        if mode == "text":
            return self._get_email_text(prompt)
        elif mode == "voice":
            return self._get_email_voice()
        elif mode == "image":
            return self._get_email_image()
        else:
            raise ValueError(f"Modo inválido: {mode}")

    def get_placa(self, mode: InputMode = "text", prompt: str = "Placa vehicular") -> str:
        """
        Obtiene placa vehicular por el modo especificado.
        
        Args:
            mode: "text", "voice", "image", "auto"
            prompt: Mensaje para el usuario
        
        Returns:
            Placa válida
        """
        if mode == "auto":
            mode = self._select_mode()

        if mode == "text":
            return self._get_placa_text(prompt)
        elif mode == "voice":
            return self._get_placa_voice()
        elif mode == "image":
            return self._get_placa_image()
        else:
            raise ValueError(f"Modo inválido: {mode}")

    def get_generic(self, field_name: str, mode: InputMode = "text",
                    validator=None) -> str:
        """
        Obtiene cualquier dato genérico.
        
        Args:
            field_name: Nombre del campo
            mode: Modo de entrada
            validator: Función de validación opcional
        
        Returns:
            Dato ingresado
        """
        if mode == "auto":
            mode = self._select_mode()

        if mode == "text":
            while True:
                valor = input(f"  {field_name}: ").strip()
                if not valor:
                    print(f"  [!] {field_name} es requerido")
                    continue
                if validator and not validator(valor):
                    print(f"  [!] Formato inválido para {field_name}")
                    continue
                return valor

        elif mode == "voice":
            if not self.voice:
                raise VoiceInputError("Entrada por voz no disponible")
            print(f"\n  🎤 Di tu {field_name}...")
            texto = self.voice.listen_and_transcribe(duration=5)
            return texto

        elif mode == "image":
            if not self.ocr:
                raise OCRError("Entrada por imagen no disponible")
            print(f"\n  📷 Toma foto con {field_name}...")
            # Aquí iría la captura de imagen
            raise NotImplementedError("Captura de imagen en desarrollo")

    # ──────────────────────────────────────────────────────────────
    # Métodos internos por modo
    # ──────────────────────────────────────────────────────────────

    def _get_curp_text(self, prompt):
        """Obtiene CURP por texto."""
        while True:
            curp = input(f"  {prompt} (18 caracteres): ").strip().upper()
            if self._validar_curp(curp):
                return curp
            print("  [!] CURP inválida (debe ser 18 caracteres, formato: AAAA######HAAAAA##)")

    def _get_curp_voice(self):
        """Obtiene CURP por voz."""
        if not self.voice:
            raise VoiceInputError("Entrada por voz no disponible")
        return self.voice.get_curp_interactive()

    def _get_curp_image(self):
        """Obtiene CURP por imagen."""
        if not self.ocr:
            raise OCRError("Entrada por imagen no disponible")

        print("\n  📷 Opciones:")
        print("  1) Tomar foto de credencial")
        print("  2) Seleccionar archivo de imagen")

        opcion = input("  Opción: ").strip()

        if opcion == "2":
            ruta = input("  Ruta de la imagen: ").strip()
            if os.path.exists(ruta):
                data = self.ocr.extract_from_screenshot(ruta)
                if data["curp"]:
                    return data["curp"]
                else:
                    raise OCRError("No se pudo extraer CURP de la imagen")
            else:
                raise FileNotFoundError(f"Archivo no encontrado: {ruta}")
        else:
            raise NotImplementedError("Captura de cámara en desarrollo")

    def _get_email_text(self, prompt):
        """Obtiene email por texto."""
        while True:
            email = input(f"  {prompt}: ").strip()
            if "@" in email and "." in email:
                return email
            print("  [!] Email inválido")

    def _get_email_voice(self):
        """Obtiene email por voz."""
        if not self.voice:
            raise VoiceInputError("Entrada por voz no disponible")
        return self.voice.get_email_interactive()

    def _get_email_image(self):
        """Obtiene email por imagen."""
        if not self.ocr:
            raise OCRError("Entrada por imagen no disponible")

        ruta = input("  Ruta de la imagen con email: ").strip()
        if os.path.exists(ruta):
            data = self.ocr.extract_from_screenshot(ruta)
            if data["email"]:
                return data["email"]
            else:
                raise OCRError("No se pudo extraer email de la imagen")
        else:
            raise FileNotFoundError(f"Archivo no encontrado: {ruta}")

    def _get_placa_text(self, prompt):
        """Obtiene placa por texto."""
        while True:
            placa = input(f"  {prompt} (ej: ABC1234): ").strip().upper()
            if len(placa) >= 6:  # Validación básica
                return placa
            print("  [!] Placa inválida")

    def _get_placa_voice(self):
        """Obtiene placa por voz."""
        if not self.voice:
            raise VoiceInputError("Entrada por voz no disponible")

        print("\n  🎤 Di tu placa vehicular...")
        print("  Ejemplo: 'A B C uno dos tres cuatro'")

        texto = self.voice.listen_and_transcribe(duration=5)
        placa = self.voice.extract_placa(texto)

        if placa:
            return placa
        else:
            # Fallback: usar texto completo limpio
            placa_limpia = texto.upper().replace(" ", "")[:7]
            return placa_limpia

    def _get_placa_image(self):
        """Obtiene placa por imagen."""
        if not self.ocr:
            raise OCRError("Entrada por imagen no disponible")

        ruta = input("  Ruta de imagen de tarjeta de circulación: ").strip()
        if os.path.exists(ruta):
            texto = self.ocr.extract_from_image(ruta)
            # Buscar patrón de placa en el texto
            match = re.search(r'([A-Z]{3}\d{4})', texto)
            if match:
                return match.group(1)
            else:
                raise OCRError("No se pudo extraer placa de la imagen")
        else:
            raise FileNotFoundError(f"Archivo no encontrado: {ruta}")

    def _select_mode(self) -> str:
        """Permite al usuario seleccionar el modo de entrada."""
        print("\n  Selecciona modo de entrada:")
        print("  1) Texto (teclado)")

        if self.voice:
            print("  2) Voz (micrófono)")

        if self.ocr:
            print("  3) Imagen (foto/archivo)")

        opcion = input("  Opción: ").strip()

        if opcion == "1":
            return "text"
        elif opcion == "2" and self.voice:
            return "voice"
        elif opcion == "3" and self.ocr:
            return "image"
        else:
            print("  [!] Opción inválida, usando texto")
            return "text"

    def _validar_curp(self, curp: str) -> bool:
        """Valida formato de CURP."""
        if len(curp) != 18:
            return False
        pattern = r'^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$'
        return bool(re.match(pattern, curp))
