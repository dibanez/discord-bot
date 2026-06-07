# Imagen ligera: solo proveedores de transcripción por API (openai, voxtral).
# El proveedor 'whisper' local (PyTorch) NO se incluye; ver requirements-whisper.txt.
FROM python:3.12-slim

# ffmpeg: necesario para que pydub procese y comprima el audio (export a MP3).
# git: necesario para instalar py-cord desde el fork de vito1317 (install VCS en
#      requirements.txt). Quitar si se vuelve a un release oficial de py-cord en PyPI.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias primero para aprovechar la caché de capas de Docker.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación.
COPY bot.py transcription.py drive_upload.py ./

# Carpeta de salida de transcripciones (se recomienda montarla como volumen).
RUN mkdir -p /app/recordings

# Ejecutar como usuario sin privilegios.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Logs sin búfer para que aparezcan en tiempo real en Dokploy.
ENV PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
