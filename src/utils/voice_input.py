"""
utils/voice_input.py
Reconocimiento de voz local usando Whisper (OpenAI)

Funcionalidades:
  - Grabación de audio desde micrófono
  - Transcripción con Whisper (modelos locales)
  - Extracción de datos específicos (CURP, correo, placa, etc.)
  - Validación de formatos
"""

import os
import re
import tempfile

from src.exceptions import VoiceInputError

try:
    import numpy as np  # noqa: F401
    import sounddevice as sd
    import soundfile as sf
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


class VoiceInput:
    """Reconocimiento de voz local con Whisper."""

    def __init__(self, model_size="base"):
        """
        Inicializa el reconocedor de voz.
        
        Args:
            model_size: Tamaño del modelo Whisper
                       "tiny" - Más rápido, menos preciso
                       "base" - Balance (recomendado)
                       "small" - Más preciso, más lento
                       "medium" - Muy preciso, lento
                       "large" - Máxima precisión, muy lento
        """
        if not WHISPER_AVAILABLE:
            raise VoiceInputError(
                "Whisper no está instalado. Instálalo con:\n"
                "pip install openai-whisper sounddevice soundfile"
            )

        self.model_size = model_size
        self.model = None
        self.sample_rate = 16000  # Whisper requiere 16kHz

        print(f"  [VOZ] Cargando modelo Whisper '{model_size}'...")
        try:
            self.model = whisper.load_model(model_size)
            print("  [VOZ] Modelo cargado [OK]")
        except Exception as e:
            raise VoiceInputError(f"Error cargando modelo Whisper: {e}")

    def record_audio(self, duration=5, countdown=True):
        """
        Graba audio desde el micrófono.
        
        Args:
            duration: Duración en segundos
            countdown: Mostrar cuenta regresiva
        
        Returns:
            Path al archivo de audio temporal
        """
        if countdown:
            print("  [VOZ] 🎤 Grabando en 3...")
            import time
            for i in range(3, 0, -1):
                print(f"  [VOZ] {i}...")
                time.sleep(1)

        print(f"  [VOZ] 🔴 GRABANDO ({duration} segundos)...")

        try:
            # Grabar audio
            recording = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32'
            )
            sd.wait()  # Esperar a que termine

            # Guardar en archivo temporal (se limpia en transcribe())
            temp_path = os.path.join(tempfile.gettempdir(), f"voz_{os.urandom(4).hex()}.wav")
            sf.write(temp_path, recording, self.sample_rate)

            print("  [VOZ] [OK] Grabación completada")
            return temp_path

        except Exception as e:
            raise VoiceInputError(f"Error grabando audio: {e}")

    def transcribe(self, audio_path, language="es"):
        """
        Transcribe audio a texto usando Whisper.
        
        Args:
            audio_path: Ruta al archivo de audio
            language: Código de idioma ("es" para español)
        
        Returns:
            Texto transcrito
        """
        print("  [VOZ] 🔄 Transcribiendo...")

        try:
            result = self.model.transcribe(
                audio_path,
                language=language,
                fp16=False  # Compatibilidad con CPU
            )

            texto = result["text"].strip()
            print(f"  [VOZ] 📝 Transcripción: '{texto}'")

            # Limpiar archivo temporal
            try:
                os.remove(audio_path)
            except Exception:
                pass

            return texto

        except Exception as e:
            raise VoiceInputError(f"Error transcribiendo audio: {e}")

    def listen_and_transcribe(self, duration=5, language="es"):
        """
        Graba y transcribe en un solo paso.
        
        Args:
            duration: Duración de grabación en segundos
            language: Idioma
        
        Returns:
            Texto transcrito
        """
        audio_path = self.record_audio(duration=duration)
        return self.transcribe(audio_path, language=language)

    # ──────────────────────────────────────────────────────────────
    # Extractores específicos de datos
    # ──────────────────────────────────────────────────────────────

    def extract_curp(self, texto):
        """
        Extrae CURP del texto transcrito.
        
        Args:
            texto: Texto transcrito
        
        Returns:
            CURP encontrada o None
        """
        # Limpiar texto: remover espacios entre letras/números
        texto_limpio = texto.upper().replace(" ", "").replace("-", "")

        # Patrón CURP: 4 letras + 6 dígitos + H/M + 5 letras + 1 letra/dígito + 1 dígito
        pattern = r'([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)'
        match = re.search(pattern, texto_limpio)

        if match:
            curp = match.group(1)
            from src.utils.pii import sanitize_curp
            print(f"  [VOZ] [OK] CURP detectada: {sanitize_curp(curp)}")
            return curp

        # Intentar extraer letra por letra si el usuario deletreó
        # Ejemplo: "A B C D uno dos tres cuatro..."
        texto_numeros = self._convertir_numeros_texto(texto)
        texto_limpio2 = texto_numeros.upper().replace(" ", "")
        match2 = re.search(pattern, texto_limpio2)

        if match2:
            curp = match2.group(1)
            from src.utils.pii import sanitize_curp
            print(f"  [VOZ] [OK] CURP detectada (deletreada): {sanitize_curp(curp)}")
            return curp

        print("  [VOZ] [!] No se detectó CURP válida")
        return None

    def extract_email(self, texto):
        """
        Extrae email del texto transcrito.
        
        Args:
            texto: Texto transcrito
        
        Returns:
            Email encontrado o None
        """
        # Limpiar texto
        texto_limpio = texto.lower().replace(" ", "")

        # Reemplazos comunes de voz a texto
        texto_limpio = texto_limpio.replace("arroba", "@")
        texto_limpio = texto_limpio.replace("punto", ".")

        # Patrón email
        pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        match = re.search(pattern, texto_limpio)

        if match:
            email = match.group(1)
            print(f"  [VOZ] [OK] Email detectado: {email}")
            return email

        print("  [VOZ] [!] No se detectó email válido")
        return None

    def extract_placa(self, texto):
        """
        Extrae placa vehicular del texto.
        
        Args:
            texto: Texto transcrito
        
        Returns:
            Placa encontrada o None
        """
        # Limpiar texto
        texto_limpio = texto.upper().replace(" ", "").replace("-", "")

        # Patrón placa: 3 letras + 4 números (formato común México)
        pattern = r'([A-Z]{3}\d{4})'
        match = re.search(pattern, texto_limpio)

        if match:
            placa = match.group(1)
            print(f"  [VOZ] [OK] Placa detectada: {placa}")
            return placa

        print("  [VOZ] [!] No se detectó placa válida")
        return None

    def _convertir_numeros_texto(self, texto):
        """
        Convierte números en texto a dígitos.
        Ejemplo: "uno dos tres" -> "123"
        """
        numeros = {
            "cero": "0", "uno": "1", "dos": "2", "tres": "3",
            "cuatro": "4", "cinco": "5", "seis": "6", "siete": "7",
            "ocho": "8", "nueve": "9"
        }

        texto_convertido = texto.lower()
        for palabra, digito in numeros.items():
            texto_convertido = texto_convertido.replace(palabra, digito)

        return texto_convertido

    def get_curp_interactive(self, max_intentos=3):
        """
        Obtiene CURP por voz de forma interactiva.
        
        Args:
            max_intentos: Número máximo de intentos
        
        Returns:
            CURP válida
        """
        print("\n  [VOZ] 🎤 Voy a grabar tu CURP")
        print("  [VOZ] Puedes decirla completa o deletrearla")
        print("  [VOZ] Ejemplo: 'A B C D uno dos tres cuatro cinco seis...'")

        for intento in range(1, max_intentos + 1):
            print(f"\n  [VOZ] Intento {intento}/{max_intentos}")

            texto = self.listen_and_transcribe(duration=8)
            curp = self.extract_curp(texto)

            if curp:
                # Validar formato
                if self._validar_curp(curp):
                    return curp
                else:
                    print("  [VOZ] [!] CURP con formato inválido, intenta de nuevo")
            else:
                print("  [VOZ] [!] No se detectó CURP, intenta de nuevo")

        raise VoiceInputError("No se pudo obtener CURP válida por voz")

    def get_email_interactive(self, max_intentos=3):
        """
        Obtiene email por voz de forma interactiva.
        
        Args:
            max_intentos: Número máximo de intentos
        
        Returns:
            Email válido
        """
        print("\n  [VOZ] 🎤 Voy a grabar tu correo electrónico")
        print("  [VOZ] Di 'arroba' para @ y 'punto' para .")
        print("  [VOZ] Ejemplo: 'juan punto perez arroba gmail punto com'")

        for intento in range(1, max_intentos + 1):
            print(f"\n  [VOZ] Intento {intento}/{max_intentos}")

            texto = self.listen_and_transcribe(duration=6)
            email = self.extract_email(texto)

            if email and "@" in email and "." in email:
                return email
            else:
                print("  [VOZ] [!] No se detectó email válido, intenta de nuevo")

        raise VoiceInputError("No se pudo obtener email válido por voz")

    def _validar_curp(self, curp):
        """Valida formato de CURP."""
        pattern = r'^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$'
        return bool(re.match(pattern, curp))


# ──────────────────────────────────────────────────────────────
# Función de utilidad para pruebas
# ──────────────────────────────────────────────────────────────

def test_voice_input():
    """Función de prueba del reconocimiento de voz."""
    try:
        voice = VoiceInput(model_size="base")

        print("\n=== TEST DE RECONOCIMIENTO DE VOZ ===\n")

        # Test 1: Transcripción simple
        print("Test 1: Di algo...")
        texto = voice.listen_and_transcribe(duration=3)
        print(f"Resultado: {texto}\n")

        # Test 2: CURP
        print("Test 2: Di tu CURP...")
        curp = voice.get_curp_interactive(max_intentos=2)
        print(f"CURP obtenida: {curp}\n")

        # Test 3: Email
        print("Test 3: Di tu email...")
        email = voice.get_email_interactive(max_intentos=2)
        print(f"Email obtenido: {email}\n")

        print("=== TESTS COMPLETADOS ===")

    except VoiceInputError as e:
        print(f"Error: {e}")
    except KeyboardInterrupt:
        print("\nTest cancelado por usuario")


if __name__ == "__main__":
    test_voice_input()
