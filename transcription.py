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
import math
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
# gpt-4o-transcribe rechaza además cualquier audio de más de 1400 s (~23 min) por
# petición, independientemente del tamaño. Troceamos también por duración.
MAX_API_AUDIO_MS = 1400 * 1000

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


# Margen de seguridad: apuntamos por debajo del límite porque el bitrate real del
# MP3 varía ligeramente por trozo (cabecera + VBR) y no queremos rozar los 25 MB.
_API_CHUNK_TARGET_RATIO = 0.9

# Solape entre trozos consecutivos: cada trozo (salvo el primero) empieza un poco
# antes para que una palabra cortada justo en la frontera aparezca entera en el
# trozo siguiente. Al unir el texto se detecta y elimina la parte repetida.
_API_CHUNK_OVERLAP_MS = 2000
# Ventana máxima (en palabras) donde buscamos la zona solapada al coser dos trozos.
_API_STITCH_MAX_WORDS = 30


def _split_audio_for_api(mp3_path, size_bytes):
    """Parte un MP3 demasiado grande en trozos que caben bajo los límites de la API.

    Calcula cuántos trozos hacen falta para no superar NI el tamaño (25 MB) NI la
    duración máxima por petición, y divide por tiempo en segmentos de igual
    duración. Cada trozo posterior al primero arranca ``_API_CHUNK_OVERLAP_MS``
    antes para solapar con el anterior y no perder palabras en las fronteras.
    Devuelve la lista de rutas de los trozos generados (archivos temporales).
    """
    from pydub import AudioSegment

    audio = AudioSegment.from_file(mp3_path)
    duration_ms = len(audio)

    # Nº de trozos necesario por cada límite; nos quedamos con el mayor.
    by_size = math.ceil(size_bytes / (MAX_API_AUDIO_BYTES * _API_CHUNK_TARGET_RATIO))
    by_duration = math.ceil(duration_ms / (MAX_API_AUDIO_MS * _API_CHUNK_TARGET_RATIO))
    num_chunks = max(2, by_size, by_duration)
    chunk_ms = math.ceil(duration_ms / num_chunks)

    base = os.path.splitext(mp3_path)[0]
    paths = []
    for i in range(num_chunks):
        # El primer trozo empieza en su sitio; los demás retroceden el solape.
        start = i * chunk_ms if i == 0 else i * chunk_ms - _API_CHUNK_OVERLAP_MS
        segment = audio[start:(i + 1) * chunk_ms]
        if len(segment) == 0:
            break
        chunk_path = f"{base}_chunk{i}.mp3"
        segment.export(chunk_path, format="mp3", bitrate="48k")
        paths.append(chunk_path)
    return paths


def _normalize_word(word):
    """Minúsculas y sin puntuación en los extremos, para comparar solapes."""
    return word.lower().strip(".,;:!?¡¿\"'()[]…—-")


def _stitch_words(prev_words, next_words):
    """Une la transcripción acumulada con la del trozo siguiente sin duplicar.

    Busca el mayor solape entre el final de ``prev_words`` y el principio de
    ``next_words`` (comparando palabras normalizadas) y descarta la repetición,
    quedándose con la versión limpia del trozo siguiente. Tolera unas pocas
    palabras "colgando" al final del trozo previo (típicamente una palabra
    cortada por la frontera), que se descartan al coser.
    """
    if not prev_words:
        return list(next_words)
    if not next_words:
        return list(prev_words)

    for skip in range(0, 4):  # palabras sobrantes toleradas al final de prev
        avail = len(prev_words) - skip
        if avail <= 0:
            break
        max_k = min(_API_STITCH_MAX_WORDS, avail, len(next_words))
        for k in range(max_k, 1, -1):  # exigimos k>=2 para no coser por casualidad
            prev_tail = [_normalize_word(w) for w in prev_words[avail - k:avail]]
            next_head = [_normalize_word(w) for w in next_words[:k]]
            if prev_tail == next_head:
                # Descarta el solape (y el sobrante) de prev; next lo aporta limpio.
                return prev_words[:avail - k] + list(next_words)

    # Sin solape detectable: concatenamos tal cual.
    return list(prev_words) + list(next_words)


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

    api_call = _transcribe_openai if canonical == "openai" else _transcribe_voxtral

    # Para las APIs en la nube comprimimos y validamos el tamaño.
    prepared = _prepare_audio_for_api(audio_path)
    chunks = []
    try:
        size = os.path.getsize(prepared)
        from pydub import AudioSegment
        duration_ms = len(AudioSegment.from_file(prepared))
        if size <= MAX_API_AUDIO_BYTES and duration_ms <= MAX_API_AUDIO_MS:
            return api_call(prepared, language)

        # El audio supera el límite de tamaño (25 MB) o de duración: lo partimos
        # en trozos (con solape) que quepan, transcribimos cada uno y cosemos el
        # texto sin duplicar la zona solapada de las fronteras.
        chunks = _split_audio_for_api(prepared, size)
        merged = []
        for chunk in chunks:
            text = api_call(chunk, language)
            if text:
                merged = _stitch_words(merged, text.split())
        return " ".join(merged).strip()
    finally:
        for tmp in [prepared, *chunks]:
            if tmp != audio_path and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


async def transcribe_audio_file(audio_path, provider=None, language="es"):
    """Transcribe ``audio_path`` con el proveedor indicado.

    Se ejecuta en un hilo aparte para no bloquear el bucle de eventos de Discord.
    Devuelve el texto transcrito (posiblemente cadena vacía si no hay voz).
    Lanza excepción si el proveedor no está configurado o falla la API.
    """
    return await asyncio.to_thread(_transcribe_sync, audio_path, provider, language)
