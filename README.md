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

---

## 📋 Requisitos

- Python 3.8+
- Un bot de Discord con los siguientes permisos:
  - Leer mensajes y mensajes directos.
  - Enviar mensajes y mensajes embebidos.
  - Gestionar apodos.
  - Gestionar roles.
- Una hoja de cálculo de Google Sheets con:
  - Acceso compartido a la cuenta de servicio.
  - Formato de columnas: `Clave`, `Nombre Discord`, `Rol Asignado`.

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
