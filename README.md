# Discord Verification Bot

Este bot verifica a nuevos miembros de un servidor de Discord usando una hoja de cálculo de Google Sheets.

## Características
- Solicita una clave por mensaje privado.
- Busca esa clave en Google Sheets.
- Si es válida, cambia el apodo y asigna un rol al usuario.

## Requisitos
- Python 3.8+
- Un bot de Discord con permisos de cambiar nicknames y asignar roles.
- Hoja de Google Sheets compartida con la cuenta de servicio de Google.

## Uso
1. Crea y configura tu archivo `.env`.
2. Agrega tu `credentials.json` de Google en la raíz del proyecto.
3. Ejecuta el bot con `python bot.py`.

## Estructura esperada del Sheet

| Clave  | Nombre Discord | Rol Asignado  |
|--------|----------------|---------------|
| ABC123 | David Ibañez   | Desarrollador |

