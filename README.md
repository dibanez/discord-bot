# 🤖 Discord Verification Bot

Bot de Discord para **verificar usuarios nuevos** mediante una **clave** almacenada en una **hoja de cálculo de Google Sheets**, asignarles el rol correspondiente y permitirles solicitar soporte si tienen problemas.

---

## ✨ Características

- ✅ Verifica a nuevos miembros al entrar en el servidor.
- 📩 Solicita una clave por mensaje privado al nuevo usuario.
- 🔍 Busca la clave en Google Sheets.
- 🧑‍💼 Si es válida:
  - Cambia su apodo.
  - Asigna el rol especificado.
- ❌ Si la clave no es válida, notifica al usuario y a los administradores.
- 🔐 Comando `!testclave` para que los administradores comprueben manualmente claves.
- 🆘 Comando `!soporte` para que **cualquier usuario** pueda enviar una solicitud privada de ayuda al equipo de admins.
- 🎙️ **Nuevos comandos de grabación de audio y transcripción:**
  - `!conectar` - Conecta el bot al canal de voz en el que estás (o `!conectar [canal]`)
  - `!desconectar` - Desconecta el bot del canal de voz
  - `!grabar [proveedor] [nombre_archivo]` - Inicia la grabación automática de audio
  - `!parar` - Detiene la grabación y procesa la transcripción
  - `!transcribir [proveedor] [nombre_archivo]` - Transcribe archivos de audio adjuntos
  - `!estado` - Muestra el estado actual de conexiones y grabaciones
- 🧠 **Transcripción con múltiples proveedores** (seleccionables por comando):
  - `openai` - API de OpenAI con el modelo `gpt-4o-transcribe` (por defecto)
  - `voxtral` - API de Mistral con el modelo Voxtral (`voxtral-mini-latest`)
  - `whisper` - Modelo Whisper ejecutado en local, sin conexión (fallback)

---

## 📋 Requisitos

- Python 3.8+
- Un bot de Discord con los siguientes permisos:
  - Leer mensajes y mensajes directos.
  - Enviar mensajes y mensajes embebidos.
  - Gestionar apodos.
  - Gestionar roles.
  - **Conectar** y **Hablar** en canales de voz (para grabación).
- Una hoja de cálculo de Google Sheets con:
  - Acceso compartido a la cuenta de servicio.
  - Formato de columnas: `Clave`, `Nombre Discord`, `Rol Asignado`.
- **Dependencias adicionales para grabación de audio:**
  - `openai` - Transcripción con `gpt-4o-transcribe` y generación de resúmenes
  - `mistralai` - Transcripción con Voxtral
  - `openai-whisper` - Transcripción local (fallback sin conexión)
  - `pydub` / `ffmpeg-python` - Para procesamiento y compresión de audio
  - `PyNaCl` - Para funcionalidad de voz en Discord
- **Variables de entorno para transcripción** (ver `.env`):
  - `DEFAULT_TRANSCRIPTION_PROVIDER` - Proveedor por defecto: `openai`, `voxtral` o `whisper`
  - `OPENAI_API_KEY` - Necesaria para `openai` y para los resúmenes
  - `MISTRAL_API_KEY` - Necesaria para `voxtral`
  - `OPENAI_TRANSCRIBE_MODEL`, `VOXTRAL_MODEL`, `WHISPER_MODEL` - Modelos configurables

---

## ⚙️ Instalación

1. Clona este repositorio:

```bash
git clone https://github.com/tuusuario/discord-verification-bot.git
cd discord-verification-bot
```

---

## Uso
1. Crea y configura tu archivo `.env` (puedes partir de `.env.example`).
2. Agrega tu `credentials.json` de Google en la raíz del proyecto.
3. Ejecuta el bot con `python bot.py`.

---

## 🐳 Despliegue con Docker / Dokploy

El proyecto incluye `Dockerfile` y `docker-compose.yml`. La imagen es **ligera**
(solo proveedores de transcripción por API: `openai` y `voxtral`); no incluye
PyTorch ni el Whisper local.

### Local con Docker Compose

```bash
cp .env.example .env   # y rellena los valores
docker compose up -d --build
docker compose logs -f
```

Las credenciales de Google se pueden aportar de dos formas:
- **Recomendada**: pega el contenido de `credentials.json` en la variable
  `GOOGLE_CREDENTIALS_JSON` (JSON en una línea o en base64). El bot crea el
  archivo al arrancar.
- **Alternativa**: descomenta el montaje de `./credentials.json` en
  `docker-compose.yml`.

### Dokploy

1. Crea una aplicación de tipo **Compose** (o **Dockerfile**) apuntando a este repo.
2. En la pestaña **Environment**, pega las variables de `.env.example` con tus
   valores reales (incluida `GOOGLE_CREDENTIALS_JSON`). Dokploy las inyecta en el
   `.env` que lee `docker-compose.yml`.
3. (Opcional) Mantén el volumen `recordings` para conservar las transcripciones
   entre despliegues.
4. Despliega. Revisa los logs para ver `🟢 Bot iniciado correctamente`.

> El proveedor `whisper` (local) no está disponible en la imagen Docker. Si lo
> necesitas, instala las dependencias extra con `pip install -r requirements-whisper.txt`
> en un entorno propio (la imagen crecería a varios GB por PyTorch).

---

## Estructura esperada del Sheet

| Clave  | Nombre Discord | Rol Asignado  |
|--------|----------------|---------------|
| ABC123 | David Ibañez   | Desarrollador |

---

## Ejecuta el bot

```bash
python bot.py
```

---

## 🧪 Pruebas (Testing)

Este proyecto incluye un conjunto de pruebas unitarias para asegurar la calidad y el correcto funcionamiento del bot.

Para ejecutar las pruebas, sitúate en el directorio raíz del proyecto y ejecuta el siguiente comando en tu terminal:

```bash
python -m unittest discover tests
```

Esto descubrirá y ejecutará automáticamente todas las pruebas unitarias ubicadas en el directorio `tests/`. Asegúrate de tener todas las dependencias del proyecto instaladas, aunque las pruebas unitarias están diseñadas para mockear dependencias externas como la API de Discord y Google Sheets.

---

## 🎙️ Funcionalidades de Grabación de Audio

> ⚠️ **La grabación EN VIVO está deshabilitada temporalmente.** Discord forzó el cifrado
> de extremo a extremo en voz (E2EE/DAVE, marzo 2026) y la librería todavía no puede
> capturar ese audio ([py-cord issue #3139](https://github.com/Pycord-Development/pycord/issues/3139)).
> Los comandos `!conectar` y `!grabar` responden con un aviso. Para reactivarla cuando
> haya fix upstream: fija la versión corregida de py-cord y pon `LIVE_RECORDING_ENABLED=true`.
>
> ✅ **Mientras tanto, usa `!transcribir`**: graba la reunión con otra herramienta
> (Craig, OBS, el móvil…) y sube el archivo para obtener transcripción y resumen.

### Comandos de Grabación (Solo Administradores)

- **`!conectar`** - Conecta el bot al canal de voz en el que estás. También `!conectar [canal]` para indicarlo por nombre.
- **`!desconectar`** - Desconecta el bot del canal de voz de este servidor
- **`!grabar [proveedor] [nombre_archivo_opcional]`** - Inicia grabación automática.
  El `proveedor` es opcional (`openai` / `voxtral` / `whisper`); si se omite se usa el de por defecto.
- **`!parar`** - Detiene la grabación y genera transcripción
- **`!transcribir [proveedor] [nombre_archivo_opcional]`** - Transcribe archivos de audio adjuntos.
  El `proveedor` es opcional; ejemplos: `!transcribir voxtral mi_reunion`, `!transcribir openai`.
- **`!estado`** - Muestra el estado actual de conexiones y grabaciones

> Los comandos de voz se usan **dentro del servidor** (en un canal de texto); el bot
> ya sabe de qué servidor se trata, por eso no hace falta indicar el nombre del servidor.

### Proceso de Grabación

1. **Conectar**: El bot se conecta a un canal de voz específico
2. **Grabar**: Inicia la grabación automática de todas las voces en el canal
3. **Procesar**: Al detener, el bot procesa automáticamente el audio
4. **Transcribir**: Genera una transcripción con el proveedor elegido (OpenAI `gpt-4o-transcribe`, Mistral Voxtral o Whisper local)
5. **Guardar**: Los archivos se guardan en la carpeta `recordings/`

### Archivos Generados

- **Audio**: Archivos WAV con el audio grabado
- **Transcripción**: Archivos Markdown con la transcripción completa
- **Metadatos**: Información sobre participantes, duración y fecha

### Formatos de Audio Soportados

- **Grabación**: WAV, PCM (generado automáticamente)
- **Transcripción manual**: WAV, MP3, M4A, OGG, FLAC
