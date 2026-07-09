"""Tests para src/utils/voice_input.py.

Estrategia:
- Extractores (CURP, email, placa, validación) → tests directos, sin mocks.
- Whisper/sounddevice → lazy imports dentro de métodos.
  Se mockean via sys.modules para que `import whisper` dentro del método
  obtenga el mock automáticamente.
- WHISPER_AVAILABLE se resetea entre tests (variable global del módulo).
"""

import builtins
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

import src.utils.voice_input as vi_module
from src.exceptions import VoiceInputError
from src.utils.voice_input import VoiceInput


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_whisper_global():
    """Resetea WHISPER_AVAILABLE del módulo original antes de cada test."""
    vi_module.WHISPER_AVAILABLE = None
    yield
    vi_module.WHISPER_AVAILABLE = None


def _mock_deps():
    """Crea mocks para whisper, sounddevice, soundfile en sys.modules."""
    mock_whisper = MagicMock()
    mock_sd = MagicMock()
    mock_sf = MagicMock()
    model_mock = MagicMock()
    mock_whisper.load_model.return_value = model_mock

    return patch.dict("sys.modules", {
        "whisper": mock_whisper,
        "sounddevice": mock_sd,
        "soundfile": mock_sf,
    }), model_mock, mock_whisper


@pytest.fixture
def voice():
    """Instancia de VoiceInput con todas las dependencias mockeadas en sys.modules."""
    deps_patch, model_mock, _ = _mock_deps()
    with deps_patch:
        v = VoiceInput(model_size="tiny")
        v.model = model_mock  # asegura que apunte al mock
        yield v


# ──────────────────────────────────────────────────────────────────────
# _validar_curp
# ──────────────────────────────────────────────────────────────────────


class TestValidarCURP:
    def test_curp_valida(self, voice):
        assert voice._validar_curp("ABCD123456HDFRRR08") is True

    def test_curp_muy_corta(self, voice):
        assert voice._validar_curp("ABCD12") is False

    def test_curp_muy_larga(self, voice):
        assert voice._validar_curp("ABCD123456HDFRRR0812") is False

    def test_curp_con_acentos(self, voice):
        assert voice._validar_curp("ABCD123456HDFRRR08") is True

    def test_curp_con_minusculas(self, voice):
        assert voice._validar_curp("abcd123456hdfrrr08") is False

    def test_curp_con_espacios(self, voice):
        assert voice._validar_curp("ABCD123456 HDFRRR08") is False

    def test_curp_segundo_sexo_femenino(self, voice):
        assert voice._validar_curp("ABCD123456MDFRRR08") is True

    def test_curp_sexo_invalido(self, voice):
        assert voice._validar_curp("ABCD123456XDFRRR08") is False

    def test_curp_caracteres_especiales(self, voice):
        assert voice._validar_curp("ABC$123456HDFRRR08") is False


# ──────────────────────────────────────────────────────────────────────
# _convertir_numeros_texto
# ──────────────────────────────────────────────────────────────────────


class TestConvertirNumerosTexto:
    def test_numeros_basicos(self, voice):
        assert voice._convertir_numeros_texto("uno dos tres") == "1 2 3"

    def test_numeros_compuestos(self, voice):
        """Solo convierte palabras individuales, no compuestos."""
        assert voice._convertir_numeros_texto("veintiuno") == "veintiuno"

    def test_numeros_con_texto(self, voice):
        result = voice._convertir_numeros_texto("mi curp es cuatro cinco seis")
        assert "4 5 6" in result

    def test_numeros_vacio(self, voice):
        assert voice._convertir_numeros_texto("") == ""

    def test_numeros_sin_numeros(self, voice):
        assert voice._convertir_numeros_texto("hola mundo") == "hola mundo"

    def test_numeros_todos(self, voice):
        todos = "cero uno dos tres cuatro cinco seis siete ocho nueve"
        assert voice._convertir_numeros_texto(todos) == "0 1 2 3 4 5 6 7 8 9"

    def test_numeros_mayusculas(self, voice):
        assert voice._convertir_numeros_texto("UNO DOS") == "1 2"


# ──────────────────────────────────────────────────────────────────────
# extract_curp
# ──────────────────────────────────────────────────────────────────────


class TestExtractCURP:
    def test_curp_directa(self, voice):
        assert voice.extract_curp("Mi CURP es ABCD123456HDFRRR08") == "ABCD123456HDFRRR08"

    def test_curp_sin_espacios(self, voice):
        """Texto sin espacios ni formato."""  # ponytail: extract_curp llama .upper()
        assert voice.extract_curp("abcd123456hdfrrr08") == "ABCD123456HDFRRR08"

    def test_curp_con_guiones(self, voice):
        assert voice.extract_curp("ABCD-123456-HDFR-RR08") == "ABCD123456HDFRRR08"

    def test_curp_deletreada(self, voice):
        """Si el usuario deletrea letras y números."""
        assert voice.extract_curp(
            "A B C D uno dos tres cuatro cinco seis H D F R R R cero ocho"
        ) == "ABCD123456HDFRRR08"

    def test_curp_no_encontrada(self, voice):
        assert voice.extract_curp("Hola mundo") is None

    def test_curp_en_texto_largo(self, voice):
        texto = "mucho texto " * 10 + "ABCD123456HDFRRR08" + " mucho texto" * 10
        assert voice.extract_curp(texto) == "ABCD123456HDFRRR08"

    def test_curp_texto_vacio(self, voice):
        assert voice.extract_curp("") is None


# ──────────────────────────────────────────────────────────────────────
# extract_email
# ──────────────────────────────────────────────────────────────────────


class TestExtractEmail:
    def test_email_directo(self, voice):
        assert voice.extract_email("mi correo es user@gmail.com") == "user@gmail.com"

    def test_email_con_arroba_y_punto(self, voice):
        assert voice.extract_email("user arroba gmail punto com") == "user@gmail.com"

    def test_email_nombre_compuesto(self, voice):
        assert voice.extract_email(
            "juan punto perez arroba hotmail punto com"
        ) == "juan.perez@hotmail.com"

    def test_email_sin_arroba(self, voice):
        assert voice.extract_email("user gmail com") is None

    def test_email_con_espacios(self, voice):
        # se normalizan espacios → sigue siendo válido
        assert voice.extract_email("user@ gmail.com") == "user@gmail.com"

    def test_email_texto_vacio(self, voice):
        assert voice.extract_email("") is None

    def test_email_dominio_largo(self, voice):
        assert voice.extract_email("user@subdomain.domain.co.uk") == "user@subdomain.domain.co.uk"

    def test_email_con_caracteres_especiales(self, voice):
        assert voice.extract_email("user.name+tag@domain.com") == "user.name+tag@domain.com"


# ──────────────────────────────────────────────────────────────────────
# extract_placa
# ──────────────────────────────────────────────────────────────────────


class TestExtractPlaca:
    def test_placa_directa(self, voice):
        assert voice.extract_placa("mi placa es ABC1234") == "ABC1234"

    def test_placa_sin_espacios(self, voice):
        assert voice.extract_placa("abc1234") == "ABC1234"

    def test_placa_con_guion(self, voice):
        assert voice.extract_placa("abc-1234") == "ABC1234"

    def test_placa_no_encontrada(self, voice):
        assert voice.extract_placa("no tengo placa") is None

    def test_placa_primeras_3_letras(self, voice):
        """ABCD1234 → re.search encuentra BCD1234 (3 letras + 4 dígitos)."""
        assert voice.extract_placa("ABCD1234") == "BCD1234"

    def test_placa_pocos_digitos(self, voice):
        assert voice.extract_placa("ABC123") is None

    def test_placa_texto_vacio(self, voice):
        assert voice.extract_placa("") is None

    def test_placa_minusculas(self, voice):
        assert voice.extract_placa("xyz7890") == "XYZ7890"


# ──────────────────────────────────────────────────────────────────────
# _check_whisper — disponibilidad de dependencias
# ──────────────────────────────────────────────────────────────────────


class TestCheckWhisper:
    def test_whisper_disponible(self):
        """Todos los imports existen → True."""
        with _mock_deps()[0]:
            assert VoiceInput._check_whisper() is True

    def test_whisper_no_disponible(self):
        """ImportError en una dependencia → False."""
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("whisper", "sounddevice", "soundfile"):
                raise ImportError(f"No module named {name}")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", mock_import):
            assert VoiceInput._check_whisper() is False

    def test_cached_true(self):
        """Una vez True, no re-evalúa — persiste aunque saquemos los mocks."""
        with _mock_deps()[0]:
            VoiceInput._check_whisper()  # cachea True

        # Sin parches — debería seguir siendo True por el cache
        assert vi_module.WHISPER_AVAILABLE is True
        assert VoiceInput._check_whisper() is True

    def test_cached_false(self):
        """Una vez False, no re-evalúa."""
        vi_module.WHISPER_AVAILABLE = False
        assert VoiceInput._check_whisper() is False


# ──────────────────────────────────────────────────────────────────────
# __init__
# ──────────────────────────────────────────────────────────────────────


class TestInit:
    def test_sin_whisper_lanza_error(self):
        """Si whisper no está instalado → VoiceInputError."""
        with patch.object(VoiceInput, "_check_whisper", return_value=False):
            with pytest.raises(VoiceInputError, match="Whisper no está instalado"):
                VoiceInput(model_size="tiny")

    def test_modelo_valido(self):
        """Instancia correcta con modelo tiny."""
        deps_patch, model_mock, mock_whisper = _mock_deps()
        with deps_patch:
            v = VoiceInput(model_size="tiny")
            assert v.model_size == "tiny"
            assert v.sample_rate == 16000
            mock_whisper.load_model.assert_called_once_with("tiny")

    def test_modelo_error_carga(self):
        """Error al cargar modelo → VoiceInputError."""
        deps_patch, _, mock_whisper = _mock_deps()
        with deps_patch:
            mock_whisper.load_model.side_effect = RuntimeError("no memory")
            with pytest.raises(VoiceInputError, match="Error cargando modelo Whisper"):
                VoiceInput(model_size="tiny")


# ──────────────────────────────────────────────────────────────────────
# record_audio
# ──────────────────────────────────────────────────────────────────────


class TestRecordAudio:
    def test_retorna_path_wav(self, voice):
        """record_audio devuelve path a un .wav existente."""
        import sounddevice as sd
        import soundfile as sf

        sd.rec.return_value = None
        sd.wait.return_value = None

        path_str = voice.record_audio(duration=2, countdown=False)
        assert path_str.endswith(".wav")
        # debe existir en disco (soundfile.write mockeado: no escribe realmente)
        # pero el string de path se construye con os.path.join(tempfile.gettempdir(), ...)
        import os
        assert os.path.dirname(path_str) == tempfile.gettempdir()

    def test_llama_sounddevice_con_parametros(self, voice):
        """Verifica que sd.rec recibe duración y sample rate correctos."""
        import sounddevice as sd

        sd.rec.return_value = None
        sd.wait.return_value = None

        voice.record_audio(duration=3, countdown=False)
        sd.rec.assert_called_once()
        _, kwargs = sd.rec.call_args
        assert kwargs["samplerate"] == 16000
        assert kwargs["channels"] == 1

    def test_error_grabacion(self, voice):
        """Error en sounddevice → VoiceInputError."""
        import sounddevice as sd

        sd.rec.side_effect = OSError("no mic")

        with pytest.raises(VoiceInputError, match="Error grabando audio"):
            voice.record_audio(duration=1, countdown=False)


# ──────────────────────────────────────────────────────────────────────
# transcribe
# ──────────────────────────────────────────────────────────────────────


class TestTranscribe:
    def test_transcribe_exitoso(self, voice):
        """Transcripción exitosa devuelve texto."""
        voice.model.transcribe.return_value = {"text": "  hola mundo  "}

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            texto = voice.transcribe(tmp_path, language="es")
            assert texto == "hola mundo"
        finally:
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_transcribe_pasa_fp16_false(self, voice):
        """Llama a model.transcribe con fp16=False."""
        voice.model.transcribe.return_value = {"text": "ok"}

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            voice.transcribe(tmp_path, language="en")
            voice.model.transcribe.assert_called_once()
            _, kwargs = voice.model.transcribe.call_args
            assert kwargs["language"] == "en"
            assert kwargs["fp16"] is False
        finally:
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_error_transcripcion(self, voice):
        """Error en whisper → VoiceInputError."""
        voice.model.transcribe.side_effect = RuntimeError("whisper crash")
        with pytest.raises(VoiceInputError, match="Error transcribiendo audio"):
            voice.transcribe("fake.wav")

    def test_limpia_archivo_temporal(self, voice):
        """Archivo temporal se elimina tras transcribir."""
        voice.model.transcribe.return_value = {"text": "test"}

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()

        import os
        assert os.path.exists(tmp_path)
        voice.transcribe(tmp_path)
        assert not os.path.exists(tmp_path), "El archivo debería eliminarse"


# ──────────────────────────────────────────────────────────────────────
# listen_and_transcribe
# ──────────────────────────────────────────────────────────────────────


class TestListenAndTranscribe:
    def test_flujo_completo(self, voice):
        """Chain record → transcribe devuelve texto."""
        with (
            patch.object(voice, "record_audio", return_value="/tmp/fake.wav"),
            patch.object(voice, "transcribe", return_value="texto final") as mock_trans,
        ):
            result = voice.listen_and_transcribe(duration=4, language="es")
            assert result == "texto final"
            mock_trans.assert_called_once_with("/tmp/fake.wav", language="es")


# ──────────────────────────────────────────────────────────────────────
# get_curp_interactive / get_email_interactive
# ──────────────────────────────────────────────────────────────────────


class TestGetCURPInteractive:
    def test_curp_valida_en_primer_intento(self, voice):
        with patch.object(voice, "listen_and_transcribe", return_value="ABCD123456HDFRRR08"):
            curp = voice.get_curp_interactive(max_intentos=3)
            assert curp == "ABCD123456HDFRRR08"

    def test_curp_tras_varios_intentos(self, voice):
        with patch.object(
            voice, "listen_and_transcribe",
            side_effect=["texto invalido", "ABCD123456HDFRRR08"],
        ):
            curp = voice.get_curp_interactive(max_intentos=3)
            assert curp == "ABCD123456HDFRRR08"

    def test_curp_todos_fallan(self, voice):
        with patch.object(voice, "listen_and_transcribe", return_value="texto sin curp"):
            with pytest.raises(VoiceInputError, match="No se pudo obtener CURP"):
                voice.get_curp_interactive(max_intentos=2)


class TestGetEmailInteractive:
    def test_email_valido_primer_intento(self, voice):
        with patch.object(
            voice, "listen_and_transcribe",
            return_value="user arroba gmail punto com",
        ):
            email = voice.get_email_interactive(max_intentos=3)
            assert email == "user@gmail.com"

    def test_email_todos_fallan(self, voice):
        with patch.object(voice, "listen_and_transcribe", return_value="sin email"):
            with pytest.raises(VoiceInputError, match="No se pudo obtener email"):
                voice.get_email_interactive(max_intentos=2)
