"""Herramienta de línea de comandos: transcribe un audio, genera el resumen y
sube la transcripción a Google Drive.

Reutiliza los mismos módulos que el bot (``transcription`` para transcribir con
troceo automático, y ``drive_upload`` para subir a ``anfaia/recordings``), y
replica el prompt de resumen del bot. Pensada para ejecutarse dentro del
contenedor:

    python transcribe_file.py /app/recordings/mi_audio.wav
    python transcribe_file.py /app/recordings/mi_audio.wav openai

El resumen usa OpenAI; requiere ``OPENAI_API_KEY``. La subida a Drive requiere
las credenciales de la cuenta de servicio (``GOOGLE_CREDENTIALS_PATH``).
"""

import os
import sys

import transcription
import drive_upload

# Modelo para el resumen (el bot usa gpt-3.5-turbo).
SUMMARY_MODEL = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-3.5-turbo")


def generar_resumen(transcript):
    """Genera un resumen estructurado de la transcripción con OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not transcript.strip():
        return None
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    prompt = f"""
Analiza la siguiente transcripción y genera un resumen profesional en español.

**Transcripción:**
{transcript}

**Genera un resumen que incluya:**
1. **Resumen Ejecutivo**: Breve descripción
2. **Puntos Clave Discutidos**: Los temas principales tratados
3. **Decisiones Tomadas**: Acuerdos o decisiones alcanzadas
4. **Acciones Pendientes**: Tareas o compromisos mencionados
5. **Próximos Pasos**: Acciones a realizar después

Mantén el resumen conciso pero completo, usando un tono profesional.
"""
    try:
        response = client.chat.completions.create(
            model=SUMMARY_MODEL,
            messages=[
                {"role": "system", "content": "Eres un asistente especializado en crear resúmenes profesionales. Extrae la información clave y preséntala de forma estructurada y clara."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generando el resumen: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("Uso: python transcribe_file.py <ruta_audio> [proveedor]")
        raise SystemExit(1)

    audio_path = sys.argv[1]
    provider = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Archivo:   {audio_path}")
    print(f"Proveedor: {transcription.provider_label(provider)}")

    print("Transcribiendo (puede tardar en audios largos)...")
    transcript = transcription._transcribe_sync(audio_path, provider, "es")
    if not transcript.strip():
        print("No se obtuvo texto (¿silencio?). No se genera markdown.")
        raise SystemExit(2)
    print(f"  {len(transcript)} caracteres transcritos.")

    print("Generando resumen...")
    resumen = generar_resumen(transcript)

    md_path = os.path.splitext(audio_path)[0] + ".md"
    nombre = os.path.basename(audio_path)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Transcripción — {nombre}\n\n")
        f.write("## Resumen\n\n")
        f.write((resumen or "No se pudo generar el resumen automáticamente.") + "\n\n")
        f.write("## Transcripción completa\n\n")
        f.write(transcript + "\n\n")
        f.write(f"---\n*Transcripción: {transcription.provider_label(provider)} · "
                f"Resumen: OpenAI {SUMMARY_MODEL}*\n")
    print(f"Markdown guardado en: {md_path}")

    print("Subiendo a Google Drive...")
    links = drive_upload.upload_files([md_path])
    if links:
        for name, link in links.items():
            print(f"  Subido {name}: {link}")
    else:
        print("  No se subió nada a Drive (revisa DRIVE_UPLOAD_ENABLED y las credenciales).")


if __name__ == "__main__":
    main()
