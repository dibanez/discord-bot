"""Backends de transcripción de audio.

Soporta tres proveedores intercambiables:

- ``openai``  -> API de OpenAI con el modelo ``gpt-4o-transcribe``.
- ``voxtral`` -> API de Mistral con el modelo Voxtral (``voxtral-mini-latest``).
- ``whisper`` -> Modelo Whisper ejecutado localmente (sin conexión, como fallback).

El proveedor se selecciona por comando; si no se indica, se usa el valor de
``DEFAULT_TRANSCRIPTION_PROVIDER`` (por defecto ``openai``).

Las funciones públicas son:

- ``transcribe_audio_file(audio_path, provider=None, language="es")`` -> coroutine
- ``normalize_provider(provider)`` -> nombre canónico del proveedor
- ``is_valid_provider(provider)`` -> bool
- ``provider_label(provider)`` -> etiqueta legible para los documentos
"""

import os
import asyncio

# --- Configuración (leída de variables de entorno) ---
DEFAULT_TRANSCRIPTION_PROVIDER = os.getenv("DEFAULT_TRANSCRIPTION_PROVIDER", "openai").strip().lower()
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-transcribe")
VOXTRAL_MODEL = os.getenv("VOXTRAL_MODEL", "voxtral-mini-latest")
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "base")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Las APIs en la nube limitan la subida a 25 MB.
MAX_API_AUDIO_BYTES = 25 * 1024 * 1024

VALID_PROVIDERS = {"openai", "voxtral", "whisper"}

# Alias admitidos al escribir el proveedor en un comando.
_PROVIDER_ALIASES = {
    "openai": "openai",
    "gpt": "openai",
    "gpt-4o": "openai",
    "gpt-4o-transcribe": "openai",
    "voxtral": "voxtral",
    "mistral": "voxtral",
    "whisper": "whisper",
    "local": "whisper",
}

# Carga perezosa del modelo Whisper local (evita el coste si nunca se usa).
_whisper_model = None


def normalize_provider(provider):
    """Devuelve el nombre canónico del proveedor, o el default si viene vacío."""
    if not provider:
        return DEFAULT_TRANSCRIPTION_PROVIDER
    return _PROVIDER_ALIASES.get(provider.strip().lower(), provider.strip().lower())


def is_valid_provider(provider):
    """Indica si ``provider`` corresponde a un proveedor soportado."""
    return normalize_provider(provider) in VALID_PROVIDERS


def provider_label(provider):
    """Etiqueta legible del proveedor para los pies de los documentos."""
    canonical = normalize_provider(provider)
    labels = {
        "openai": f"OpenAI ({OPENAI_TRANSCRIBE_MODEL})",
        "voxtral": f"Mistral Voxtral ({VOXTRAL_MODEL})",
        "whisper": f"Whisper local ({WHISPER_MODEL_NAME})",
    }
    return labels.get(canonical, canonical)


def _get_whisper_model():
    """Carga (una sola vez) el modelo Whisper local."""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
        except ImportError as exc:
            raise RuntimeError(
                "El proveedor 'whisper' (local) requiere el paquete 'openai-whisper', "
                "que no está instalado. Instálalo con 'pip install openai-whisper' o usa "
                "los proveedores 'openai' / 'voxtral'."
            ) from exc
        _whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
    return _whisper_model


def _prepare_audio_for_api(audio_path):
    """Comprime el audio a MP3 mono 16 kHz para reducir el tamaño de subida.

    Los modelos de transcripción remuestrean a 16 kHz de todos modos, por lo que
    no se pierde calidad útil y el archivo cabe mucho mejor en el límite de 25 MB.

    Devuelve la ruta del MP3 generado (un archivo temporal distinto del original).
    """
    from pydub import AudioSegment

    audio = AudioSegment.from_file(audio_path)
    audio = audio.set_channels(1).set_frame_rate(16000)
    base = os.path.splitext(audio_path)[0]
    mp3_path = f"{base}_api.mp3"
    audio.export(mp3_path, format="mp3", bitrate="48k")
    return mp3_path


def _transcribe_openai(audio_path, language):
    """Transcribe con la API de OpenAI (gpt-4o-transcribe)."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY no configurada; no se puede usar el proveedor 'openai'.")
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model=OPENAI_TRANSCRIBE_MODEL,
            file=f,
            language=language,
        )
    return (response.text or "").strip()


def _transcribe_voxtral(audio_path, language):
    """Transcribe con la API de Mistral (Voxtral)."""
    if not MISTRAL_API_KEY:
        raise RuntimeError("MISTRAL_API_KEY no configurada; no se puede usar el proveedor 'voxtral'.")
    # La ruta del import cambió entre versiones del SDK de Mistral:
    # 1.x expone `from mistralai import Mistral`; 2.x lo mueve a `mistralai.client`.
    try:
        from mistralai import Mistral
    except ImportError:
        from mistralai.client import Mistral

    client = Mistral(api_key=MISTRAL_API_KEY)
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.complete(
            model=VOXTRAL_MODEL,
            file={"content": f, "file_name": os.path.basename(audio_path)},
            language=language,
        )
    return (response.text or "").strip()


def _transcribe_whisper(audio_path, language):
    """Transcribe con el modelo Whisper local."""
    model = _get_whisper_model()
    result = model.transcribe(audio_path, language=language)
    return (result.get("text") or "").strip()


def _transcribe_sync(audio_path, provider, language):
    """Implementación bloqueante de la transcripción (se ejecuta en un hilo)."""
    canonical = normalize_provider(provider)

    if canonical == "whisper":
        # Whisper local acepta el archivo tal cual, sin límite de tamaño.
        return _transcribe_whisper(audio_path, language)

    if canonical not in ("openai", "voxtral"):
        raise ValueError(f"Proveedor de transcripción desconocido: {provider!r}")

    # Para las APIs en la nube comprimimos y validamos el tamaño.
    prepared = _prepare_audio_for_api(audio_path)
    try:
        size = os.path.getsize(prepared)
        if size > MAX_API_AUDIO_BYTES:
            raise RuntimeError(
                f"El audio comprimido pesa {size / 1024 / 1024:.1f} MB y supera el límite "
                f"de 25 MB de la API. Usa el proveedor 'whisper' (local) para audios largos."
            )
        if canonical == "openai":
            return _transcribe_openai(prepared, language)
        return _transcribe_voxtral(prepared, language)
    finally:
        if prepared != audio_path and os.path.exists(prepared):
            try:
                os.remove(prepared)
            except OSError:
                pass


async def transcribe_audio_file(audio_path, provider=None, language="es"):
    """Transcribe ``audio_path`` con el proveedor indicado.

    Se ejecuta en un hilo aparte para no bloquear el bucle de eventos de Discord.
    Devuelve el texto transcrito (posiblemente cadena vacía si no hay voz).
    Lanza excepción si el proveedor no está configurado o falla la API.
    """
    return await asyncio.to_thread(_transcribe_sync, audio_path, provider, language)
