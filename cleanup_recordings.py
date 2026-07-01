"""Limpieza de grabaciones antiguas ya transcritas.

Para cada audio en la carpeta de grabaciones que cumpla LAS DOS condiciones:

  1. tiene más de ``RECORDINGS_RETENTION_DAYS`` días (por defecto 7), y
  2. ya está transcrito (existe su ``.md`` al lado),

se borran TANTO el audio como su ``.md`` (se asume que el ``.md`` ya se subió a
Drive). Los audios sin transcripción NUNCA se tocan.

Pensado para ejecutarse en un cron / schedule dentro del contenedor:

    python cleanup_recordings.py                 # carpeta por defecto (recordings)
    python cleanup_recordings.py /app/recordings # carpeta explícita

Variables de entorno:
    RECORDINGS_RETENTION_DAYS  días a conservar (por defecto 7)
    RECORDINGS_DIR             carpeta por defecto si no se pasa por argumento
    CLEANUP_DRY_RUN            "true" para solo listar sin borrar
"""

import os
import sys
import time

RETENTION_DAYS = float(os.getenv("RECORDINGS_RETENTION_DAYS", "7"))
DEFAULT_DIR = os.getenv("RECORDINGS_DIR", "recordings")
DRY_RUN = os.getenv("CLEANUP_DRY_RUN", "false").strip().lower() in ("1", "true", "yes", "si", "sí")

# Extensiones consideradas "audio de grabación".
AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".ogg", ".flac")


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DIR
    if not os.path.isdir(base):
        print(f"La carpeta no existe: {base}")
        raise SystemExit(1)

    cutoff = time.time() - RETENTION_DAYS * 86400
    borrados = 0
    liberado = 0

    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name)
        if not os.path.isfile(path):
            continue
        if os.path.splitext(name)[1].lower() not in AUDIO_EXTS:
            continue

        md_path = os.path.splitext(path)[0] + ".md"
        if not os.path.exists(md_path):
            continue  # sin transcripción -> no tocar
        if os.path.getmtime(path) > cutoff:
            continue  # todavía reciente -> no tocar

        for target in (path, md_path):
            try:
                size = os.path.getsize(target)
                if DRY_RUN:
                    print(f"[dry-run] borraría: {target} ({size/1024/1024:.1f} MB)")
                else:
                    os.remove(target)
                    print(f"Borrado: {target} ({size/1024/1024:.1f} MB)")
                borrados += 1
                liberado += size
            except OSError as e:
                print(f"No se pudo borrar {target}: {e}")

    accion = "se borrarían" if DRY_RUN else "borrados"
    print(f"Hecho. {borrados} ficheros {accion}, {liberado/1024/1024:.1f} MB "
          f"(retención: {RETENTION_DAYS:.0f} días, carpeta: {base}).")


if __name__ == "__main__":
    main()
