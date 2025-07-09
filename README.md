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
  - `!conectar [nombre_canal]` - Conecta el bot a un canal de voz específico
  - `!desconectar [nombre_servidor]` - Desconecta el bot de un canal de voz
  - `!grabar [nombre_servidor] [nombre_archivo]` - Inicia la grabación automática de audio
  - `!parar [nombre_servidor]` - Detiene la grabación y procesa la transcripción
  - `!transcribir [nombre_archivo]` - Transcribe archivos de audio adjuntos
  - `!estado` - Muestra el estado actual de conexiones y grabaciones

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
  - `whisper` - Para transcripción de audio
  - `pydub` - Para procesamiento de audio
  - `PyNaCl` - Para funcionalidad de voz en Discord

---

## ⚙️ Instalación

1. Clona este repositorio:

```bash
git clone https://github.com/tuusuario/discord-verification-bot.git
cd discord-verification-bot
```

---

## Uso
1. Crea y configura tu archivo `.env`.
2. Agrega tu `credentials.json` de Google en la raíz del proyecto.
3. Ejecuta el bot con `python bot.py`.

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

### Comandos de Grabación (Solo Administradores)

- **`!conectar [nombre_canal]`** - Conecta el bot a un canal de voz
- **`!desconectar [nombre_servidor]`** - Desconecta el bot del canal de voz
- **`!grabar [nombre_servidor] [nombre_archivo_opcional]`** - Inicia grabación automática
- **`!parar [nombre_servidor]`** - Detiene la grabación y genera transcripción
- **`!transcribir [nombre_archivo_opcional]`** - Transcribe archivos de audio adjuntos
- **`!estado`** - Muestra el estado actual de conexiones y grabaciones

### Proceso de Grabación

1. **Conectar**: El bot se conecta a un canal de voz específico
2. **Grabar**: Inicia la grabación automática de todas las voces en el canal
3. **Procesar**: Al detener, el bot procesa automáticamente el audio
4. **Transcribir**: Genera una transcripción usando Whisper AI
5. **Guardar**: Los archivos se guardan en la carpeta `recordings/`

### Archivos Generados

- **Audio**: Archivos WAV con el audio grabado
- **Transcripción**: Archivos Markdown con la transcripción completa
- **Metadatos**: Información sobre participantes, duración y fecha

### Formatos de Audio Soportados

- **Grabación**: WAV, PCM (generado automáticamente)
- **Transcripción manual**: WAV, MP3, M4A, OGG, FLAC
