import discord
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from discord.ext import commands
from discord.ext.commands import has_permissions
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import gspread
from gspread.exceptions import (
    SpreadsheetNotFound,
    WorksheetNotFound,
    APIError as GSpreadAPIError,
)
import discord
from discord.errors import (
    Forbidden as DiscordForbiddenError,
    HTTPException as DiscordHTTPException,
)
import wave
import threading
import time
from pydub import AudioSegment
import io
from openai import OpenAI
from transcription import (
    transcribe_audio_file,
    normalize_provider,
    is_valid_provider,
    provider_label,
    DEFAULT_TRANSCRIPTION_PROVIDER,
    VALID_PROVIDERS,
)

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
GOOGLE_SHEET_TAB = os.getenv("GOOGLE_SHEET_TAB")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Verification Settings ---
VERIFICATION_MAX_ATTEMPTS = int(os.getenv("VERIFICATION_MAX_ATTEMPTS", 3))
COMUNIDAD_ROLE_NAME = os.getenv("COMUNIDAD_ROLE_NAME", "Comunidad")

# --- Configurable Messages ---
# On Member Join
MSG_MEMBER_JOIN_WELCOME = os.getenv(
    "MSG_MEMBER_JOIN_WELCOME",
    "👋 ¡Bienvenido al servidor de ANFAIA!\n\n"
    "Para completar tu acceso, por favor **responde a este mensaje escribiendo tu nombre completo** (nombre y apellidos).\n"
    "📝 *Lo usaremos como tu apodo en el servidor para que todos podamos identificarte.*\n\n"
    "Si necesitas ayuda, **escribe el comando `!soporte` seguido de tu mensaje aquí mismo, en este chat privado con el bot**.\n\n"
    "Por ejemplo:\n"
    "`!soporte Tengo un problema para acceder al servidor.`\n\n"
    "Un administrador revisará tu mensaje y te responderá lo antes posible.\n\n"
    "¡Gracias por unirte a la Asociación Nacional Faro para la Aceleración de la Inteligencia Artificial!",
)
MSG_MEMBER_JOIN_TIMEOUT = os.getenv(
    "MSG_MEMBER_JOIN_TIMEOUT",
    "⏰ Se acabó el tiempo para indicar tu nombre. Si necesitas ayuda, usa `!soporte` o contacta a un administrador.",
)
MSG_MEMBER_JOIN_ERROR = os.getenv(
    "MSG_MEMBER_JOIN_ERROR", "⚠️ Hubo un error al procesar tu registro."
)
MSG_NAME_INVALID_RETRY = os.getenv(
    "MSG_NAME_INVALID_RETRY",
    "❌ El nombre indicado no es válido (debe tener al menos 2 caracteres y no superar los 32). Te quedan {attempts_left} intento(s). Por favor, escribe tu nombre completo:",
)
MSG_NAME_NO_ATTEMPTS_LEFT = os.getenv(
    "MSG_NAME_NO_ATTEMPTS_LEFT",
    "❌ Has agotado todos tus intentos. Por favor, contacta con un administrador o usa el comando `!soporte` si necesitas ayuda.",
)
MSG_NAME_SUCCESS = os.getenv(
    "MSG_NAME_SUCCESS",
    "✅ ¡Gracias, {nombre}! Te he asignado el rol `{rol_nombre}` y ya tienes acceso al servidor.",
)
MSG_NAME_ROLE_NOT_FOUND = os.getenv(
    "MSG_NAME_ROLE_NOT_FOUND",
    "⚠️ He guardado tu nombre, pero no se encontró el rol `{rol_nombre}`. Un administrador lo revisará.",
)

# Key Verification (_verify_member_key)
MSG_VERIFY_SUCCESS = os.getenv(
    "MSG_VERIFY_SUCCESS", "✅ Verificado. Se te ha asignado el rol `{rol_nombre}`."
)
MSG_VERIFY_ROLE_NOT_FOUND = os.getenv(
    "MSG_VERIFY_ROLE_NOT_FOUND",
    "⚠️ Clave correcta, pero no se encontró el rol `{rol_nombre}`.",
)
MSG_VERIFY_KEY_INCORRECT = os.getenv(
    "MSG_VERIFY_KEY_INCORRECT",
    "❌ Clave incorrecta. Contacta con un admin si crees que es un error.",
)
MSG_VERIFY_ERROR_GENERAL = os.getenv(  # Renamed from MSG_VERIFY_INTERNAL_ERROR
    "MSG_VERIFY_ERROR_GENERAL",
    "⚠️ Hubo un error interno al procesar tu clave. Intenta de nuevo o contacta a soporte.",
)
MSG_VERIFY_ERROR_CRITICAL_SHEET = os.getenv(
    "MSG_VERIFY_ERROR_CRITICAL_SHEET",
    "⚠️ Hubo un problema crítico accediendo a la hoja de verificación. Por favor, contacta a un administrador.",
)
MSG_VERIFY_ERROR_SHEET_API = os.getenv(
    "MSG_VERIFY_ERROR_SHEET_API",
    "⚠️ Hubo un problema comunicándose con Google Sheets. Intenta más tarde o contacta a un administrador.",
)
MSG_VERIFY_ERROR_PERMISSION = os.getenv(
    "MSG_VERIFY_ERROR_PERMISSION",
    "⚠️ El bot no tiene permisos suficientes para completar tu verificación. Por favor, contacta a un administrador.",
)
MSG_VERIFY_ERROR_DISCORD_API = os.getenv(
    "MSG_VERIFY_ERROR_DISCORD_API",
    "⚠️ Hubo un problema con la API de Discord durante tu verificación. Intenta más tarde o contacta a un administrador.",
)

# Admin & TestClave Command
MSG_ADMIN_REQUIRED = os.getenv(
    "MSG_ADMIN_REQUIRED",
    "❌ Necesitas permisos de Administrador para usar este comando.",
)
MSG_TESTCLAVE_USAGE = os.getenv("MSG_TESTCLAVE_USAGE", "❌ Uso: `!testclave [clave]`")
MSG_TESTCLAVE_KEY_NOT_FOUND = os.getenv(
    "MSG_TESTCLAVE_KEY_NOT_FOUND", "❌ Clave no encontrada en la hoja de cálculo."
)
MSG_TESTCLAVE_ERROR = os.getenv(
    "MSG_TESTCLAVE_ERROR", "❗ Error al probar la clave: `{e}`"
)

# Soporte Command
MSG_SOPORTE_DM_ONLY = os.getenv(
    "MSG_SOPORTE_DM_ONLY",
    "❌ Este comando solo se puede usar por mensaje privado al bot.",
)
MSG_SOPORTE_USAGE = os.getenv(
    "MSG_SOPORTE_USAGE", "❌ Debes escribir un mensaje. Uso: `!soporte [mensaje]`"
)
MSG_SOPORTE_SENT = os.getenv(
    "MSG_SOPORTE_SENT",
    "✅ Tu mensaje ha sido enviado al equipo de soporte. Te responderán pronto.",
)
MSG_SOPORTE_SERVER_NOT_DETERMINED = os.getenv(
    "MSG_SOPORTE_SERVER_NOT_DETERMINED",
    "⚠️ No se ha podido determinar tu servidor. Contacta con un administrador.",
)
MSG_SOPORTE_ERROR = os.getenv(
    "MSG_SOPORTE_ERROR", "❗ Hubo un error al enviar tu solicitud. Inténtalo más tarde."
)

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

voice_clients = {}
recording_data = {}
openai_client = None

# En despliegues (p. ej. Dokploy) es más cómodo inyectar las credenciales de
# Google por variable de entorno que montar un archivo. Si GOOGLE_CREDENTIALS_JSON
# está definida (JSON crudo o codificado en base64), se escribe a GOOGLE_CREDENTIALS_PATH.
_google_creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
if _google_creds_json and not os.path.exists(GOOGLE_CREDENTIALS_PATH):
    import base64
    content = _google_creds_json.strip()
    if not content.startswith("{"):
        # Asumimos base64 si no parece JSON directo.
        content = base64.b64decode(content).decode("utf-8")
    with open(GOOGLE_CREDENTIALS_PATH, "w", encoding="utf-8") as _cred_file:
        _cred_file.write(content)
    print("✅ Credenciales de Google escritas desde GOOGLE_CREDENTIALS_JSON")

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_PATH, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).worksheet(GOOGLE_SHEET_TAB)


@bot.event
async def on_ready():
    global log_channel
    global support_channel
    global guild
    global openai_client
    guild = discord.utils.get(bot.guilds)
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    support_channel = bot.get_channel(SUPPORT_CHANNEL_ID)

    print(f"🗣️ Proveedor de transcripción por defecto: {provider_label(DEFAULT_TRANSCRIPTION_PROVIDER)}")

    try:
        if OPENAI_API_KEY:
            openai_client = OpenAI(api_key=OPENAI_API_KEY)
            print("✅ Cliente OpenAI configurado correctamente")
        else:
            print("⚠️ OPENAI_API_KEY no configurada - resúmenes no disponibles")
    except Exception as e:
        print(f"⚠️ Error configurando OpenAI: {e}")
    
    print(f"✅ Bot listo como: {bot.user.name}")
    if log_channel:
        await log_channel.send("🟢 Bot iniciado correctamente.")


async def _verify_member_key(member, key_provided, current_sheet, current_log_channel):
    """
    Verifies the member's key, assigns role, and sends relevant messages.
    Accepts sheet and log_channel objects for testability.
    Returns True if key was found and all critical operations succeeded, False otherwise.
    """
    try:
        try:
            rows = current_sheet.get_all_records()
        except SpreadsheetNotFound:
            if current_log_channel:
                await current_log_channel.send(
                    f"❗ **ERROR CRÍTICO:** Hoja de cálculo '{GOOGLE_SHEET_NAME}' no encontrada. User: {member.name} ({member.id})"
                )
            await member.send(MSG_VERIFY_ERROR_CRITICAL_SHEET)
            return False
        except WorksheetNotFound:
            if current_log_channel:
                await current_log_channel.send(
                    f"❗ **ERROR CRÍTICO:** Pestaña '{GOOGLE_SHEET_TAB}' no encontrada en '{GOOGLE_SHEET_NAME}'. User: {member.name} ({member.id})"
                )
            await current_log_channel.send(MSG_VERIFY_ERROR_CRITICAL_SHEET)
            return False
        except GSpreadAPIError as e_gspread:
            if current_log_channel:
                await current_log_channel.send(
                    f"❗ **ERROR API GOOGLE:** {e_gspread} al leer la hoja. User: {member.name} ({member.id})"
                )
            await member.send(MSG_VERIFY_ERROR_SHEET_API)
            return False

        key_found_in_sheet = False
        for row in rows:
            if row["Clave"] == key_provided:
                key_found_in_sheet = True
                nombre = row["Nombre Discord"]
                rol_nombre = row["Rol Asignado"]

                try:
                    await member.edit(nick=nombre)
                except DiscordForbiddenError:
                    if current_log_channel:
                        await current_log_channel.send(
                            f"⚠️ **Permiso denegado:** No se pudo cambiar el apodo de {member.mention} ({member.id}) a '{nombre}'."
                        )
                except DiscordHTTPException as e_discord_http:
                    if current_log_channel:
                        await current_log_channel.send(
                            f"❗ **Error Discord API:** Al cambiar apodo de {member.mention} ({member.id}): {e_discord_http}"
                        )

                role_assigned_successfully = False
                role_to_assign = discord.utils.get(member.guild.roles, name=rol_nombre)

                if role_to_assign:
                    try:
                        await member.add_roles(role_to_assign)
                        role_assigned_successfully = True
                        await member.send(
                            MSG_VERIFY_SUCCESS.format(rol_nombre=rol_nombre)
                        )
                        if current_log_channel:
                            await current_log_channel.send(
                                f"✅ **{member.name} ({member.id})** verificado como `{nombre}` y asignado el rol `{rol_nombre}`."
                            )
                    except DiscordForbiddenError:
                        if current_log_channel:
                            await current_log_channel.send(
                                f"⚠️ **Permiso denegado:** No se pudo asignar el rol '{rol_nombre}' a {member.mention} ({member.id})."
                            )
                        # Attempt to notify user that role assignment failed
                        try:
                            await member.send(
                                MSG_VERIFY_ERROR_PERMISSION
                                + f" (No se pudo asignar el rol '{rol_nombre}')"
                            )
                        except:
                            pass  # User DMs might be closed
                    except DiscordHTTPException as e_discord_http:
                        if current_log_channel:
                            await current_log_channel.send(
                                f"❗ **Error Discord API:** Al asignar rol '{rol_nombre}' a {member.mention} ({member.id}): {e_discord_http}"
                            )
                        try:
                            await member.send(
                                MSG_VERIFY_ERROR_DISCORD_API
                                + f" (Al intentar asignar el rol '{rol_nombre}')"
                            )
                        except:
                            pass
                else:
                    await member.send(
                        MSG_VERIFY_ROLE_NOT_FOUND.format(rol_nombre=rol_nombre)
                    )
                    if current_log_channel:
                        await current_log_channel.send(
                            f"⚠️ **{member.name} ({member.id})** tenía clave válida, pero rol `{rol_nombre}` no encontrado."
                        )

                return True  # Key was found, attempted operations. Individual errors logged.

        if not key_found_in_sheet:
            # Key not found, DO NOT send DM here. Simply return False.
            # Logging of individual failed attempts can be done here if desired.
            if current_log_channel:  # Optional: Log every failed attempt from here
                await current_log_channel.send(
                    f"ℹ️ Intento de clave fallido para {member.name} ({member.id}) con clave: '{key_provided}'"
                )
            return False

    except (
        DiscordForbiddenError,
        DiscordHTTPException,
    ) as e_discord_direct_send:  # Catch errors from direct member.send calls if user blocks bot mid-process
        # This can happen if user blocks bot or DMs become unavailable after _verify_member_key started.
        if current_log_channel:
            await current_log_channel.send(
                f"❗ Error enviando DM a {member.name} ({member.id}) durante _verify_member_key (e.g. user blocked DMs): {e_discord_direct_send}"
            )
        return False  # Failed to communicate with user
    except Exception as e:
        print(f"[ERROR EN _verify_member_key] para {member.name} ({member.id}): {e}")
        if current_log_channel:
            await current_log_channel.send(
                f"❗ Error interno no esperado verificando a **{member.name} ({member.id})**: `{e}`"
            )
        try:
            await member.send(MSG_VERIFY_ERROR_GENERAL)
        except:
            pass  # User might have DMs blocked or left
        return False
    return False  # Should not be reached if logic is correct, but as a fallback.


@bot.event
async def on_member_join(member):
    try:
        try:
            await member.send(MSG_MEMBER_JOIN_WELCOME)
        except DiscordForbiddenError:
            if log_channel:
                await log_channel.send(
                    f"⚠️ No se pudo enviar DM de bienvenida a {member.mention} ({member.id}). DMs desactivados/bloqueado."
                )
            return  # Cannot proceed if welcome DM fails
        except DiscordHTTPException as e_discord_http:
            if log_channel:
                await log_channel.send(
                    f"❗ Error API Discord enviando DM de bienvenida a {member.mention} ({member.id}): {e_discord_http}"
                )
            return  # Cannot proceed

        def check(m):
            return m.author == member and isinstance(m.channel, discord.DMChannel)

        attempts_left = VERIFICATION_MAX_ATTEMPTS
        while attempts_left > 0:
            try:
                msg = await bot.wait_for("message", check=check, timeout=540.0)
            except asyncio.TimeoutError:
                try:
                    await member.send(MSG_MEMBER_JOIN_TIMEOUT)
                except (DiscordForbiddenError, DiscordHTTPException):
                    pass

                if log_channel:
                    await log_channel.send(
                        f"⏰ **{member.name} ({member.id})** no introdujo su nombre a tiempo (intento {VERIFICATION_MAX_ATTEMPTS - attempts_left + 1})."
                    )
                return

            nombre = msg.content.strip()

            # Ignorar comandos como !soporte para que sigan funcionando
            if nombre.startswith("!"):
                continue

            # Discord limita los apodos a 32 caracteres
            if len(nombre) < 2 or len(nombre) > 32:
                attempts_left -= 1
                if attempts_left > 0:
                    try:
                        await member.send(
                            MSG_NAME_INVALID_RETRY.format(attempts_left=attempts_left)
                        )
                    except (DiscordForbiddenError, DiscordHTTPException):
                        return
                    continue
                else:
                    try:
                        await member.send(MSG_NAME_NO_ATTEMPTS_LEFT)
                    except (DiscordForbiddenError, DiscordHTTPException):
                        pass
                    if log_channel:
                        await log_channel.send(
                            f"❌ **{member.name} ({member.id})** falló el registro de nombre después de {VERIFICATION_MAX_ATTEMPTS} intentos."
                        )
                    return

            # Asignar apodo
            try:
                await member.edit(nick=nombre)
            except DiscordForbiddenError:
                if log_channel:
                    await log_channel.send(
                        f"⚠️ **Permiso denegado:** No se pudo cambiar el apodo de {member.mention} ({member.id}) a '{nombre}'."
                    )
            except DiscordHTTPException as e_discord_http:
                if log_channel:
                    await log_channel.send(
                        f"❗ **Error Discord API:** Al cambiar apodo de {member.mention} ({member.id}): {e_discord_http}"
                    )

            # Asignar rol de comunidad
            role_to_assign = discord.utils.get(
                member.guild.roles, name=COMUNIDAD_ROLE_NAME
            )
            if role_to_assign:
                try:
                    await member.add_roles(role_to_assign)
                    await member.send(
                        MSG_NAME_SUCCESS.format(
                            nombre=nombre, rol_nombre=COMUNIDAD_ROLE_NAME
                        )
                    )
                    if log_channel:
                        await log_channel.send(
                            f"✅ **{member.name} ({member.id})** registrado como `{nombre}` y asignado el rol `{COMUNIDAD_ROLE_NAME}`."
                        )
                except DiscordForbiddenError:
                    if log_channel:
                        await log_channel.send(
                            f"⚠️ **Permiso denegado:** No se pudo asignar el rol '{COMUNIDAD_ROLE_NAME}' a {member.mention} ({member.id})."
                        )
                    try:
                        await member.send(
                            MSG_VERIFY_ERROR_PERMISSION
                            + f" (No se pudo asignar el rol '{COMUNIDAD_ROLE_NAME}')"
                        )
                    except:
                        pass
                except DiscordHTTPException as e_discord_http:
                    if log_channel:
                        await log_channel.send(
                            f"❗ **Error Discord API:** Al asignar rol '{COMUNIDAD_ROLE_NAME}' a {member.mention} ({member.id}): {e_discord_http}"
                        )
                    try:
                        await member.send(
                            MSG_VERIFY_ERROR_DISCORD_API
                            + f" (Al intentar asignar el rol '{COMUNIDAD_ROLE_NAME}')"
                        )
                    except:
                        pass
            else:
                await member.send(
                    MSG_NAME_ROLE_NOT_FOUND.format(rol_nombre=COMUNIDAD_ROLE_NAME)
                )
                if log_channel:
                    await log_channel.send(
                        f"⚠️ **{member.name} ({member.id})** registrado como `{nombre}`, pero rol `{COMUNIDAD_ROLE_NAME}` no encontrado."
                    )

            return

    # Specific error handlers from previous step (DiscordForbiddenError, DiscordHTTPException for on_member_join scope)
    except DiscordForbiddenError as e_forbidden:
        if log_channel:
            await log_channel.send(
                f"❗ **Error de permisos Discord (Forbidden)** en on_member_join para {member.name} ({member.id}): {e_forbidden}. Revisar permisos del bot."
            )
        try:
            await member.send(MSG_VERIFY_ERROR_PERMISSION)
        except:
            pass
    except DiscordHTTPException as e_http:
        if log_channel:
            await log_channel.send(
                f"❗ **Error HTTP Discord** en on_member_join para {member.name} ({member.id}): {e_http}. API podría tener problemas."
            )
        try:
            await member.send(MSG_VERIFY_ERROR_DISCORD_API)
        except:
            pass
    except Exception as e:  # General catch-all for on_member_join
        print(f"[ERROR GENERAL en on_member_join para {member.name} ({member.id})] {e}")
        if log_channel:
            await log_channel.send(
                f"❗ Error crítico no manejado en on_member_join para **{member.name} ({member.id})**: `{e}`"
            )
        try:
            await member.send(MSG_MEMBER_JOIN_ERROR)
        except:
            pass


async def is_bot_admin(ctx):
    """
    Checks if the command author has administrator permissions in ANY of the guilds the bot is part of.
    """
    for guild in ctx.bot.guilds:
        member = guild.get_member(ctx.author.id)
        if member and member.guild_permissions.administrator:
            return True
    return False


@bot.command(name="testclave")
async def test_clave(ctx, password: str = None):
    if not await is_bot_admin(ctx):
        await ctx.send(MSG_ADMIN_REQUIRED)
        return

    if password is None:
        await ctx.send(MSG_TESTCLAVE_USAGE)
        return

    try:
        rows = sheet.get_all_records()
        find = False

        for row in rows:
            if row["Clave"] == password.strip():
                name = row["Nombre Discord"]
                rol_name = row["Rol Asignado"]

                rol_status = "❓ No se puede verificar en DM"
                if not isinstance(ctx.channel, discord.DMChannel):
                    role = discord.utils.get(ctx.guild.roles, name=rol_name)
                    rol_status = "✅ Rol existe" if role else "⚠️ Rol no encontrado"
                else:
                    rol_find = False
                    for guild in bot.guilds:
                        role = discord.utils.get(guild.roles, name=rol_name)
                        if role:
                            rol_status = f"✅ Rol existe en {guild.name}"
                            rol_find = True
                            break
                    if not rol_find:
                        rol_status = "⚠️ Rol no encontrado en ningún servidor"

                embed = discord.Embed(
                    title="✅ Prueba de Clave",
                    description=f"Resultado para la clave: `{password}`",
                    color=0x00FF00,
                )
                embed.add_field(name="Nombre a asignar", value=name, inline=False)
                embed.add_field(name="Rol a asignar", value=rol_name, inline=True)
                embed.add_field(name="Estado del rol", value=rol_status, inline=True)
                embed.set_footer(
                    text="Esta es solo una prueba, no se ha aplicado ningún cambio"
                )

                await ctx.send(embed=embed)
                find = True

                if log_channel:
                    where = (
                        "en DM"
                        if isinstance(ctx.channel, discord.DMChannel)
                        else f"en #{ctx.channel.name}"
                    )
                    await log_channel.send(
                        f"🔍 **{ctx.author.name}** probó la clave `{password}` {where} - Asignaría: `{name}` con rol `{rol_name}`"
                    )
                break

        if not find:
            await ctx.send(MSG_TESTCLAVE_KEY_NOT_FOUND)

            if log_channel:
                where = (
                    "en DM"
                    if isinstance(ctx.channel, discord.DMChannel)
                    else f"en #{ctx.channel.name}"
                )
                await log_channel.send(
                    f"🔍 **{ctx.author.name}** probó una clave inválida {where}: `{password}`"
                )

    except Exception as e:
        print(f"[ERROR] {e}")
        await ctx.send(MSG_TESTCLAVE_ERROR.format(e=e))

        if log_channel:
            await log_channel.send(
                f"❗ Error en comando testclave por **{ctx.author.name}**: `{e}`"
            )


@bot.command(name="soporte")
async def support(ctx, *, message: str = None):
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send(MSG_SOPORTE_DM_ONLY)
        return

    if message is None:
        await ctx.send(MSG_SOPORTE_USAGE)
        return

    try:
        sended = False

        embed = discord.Embed(
            title="📩 Solicitud de Soporte",
            description=message,
            color=0x3498DB,
        )
        embed.add_field(
            name="Usuario", value=f"{ctx.author} ({ctx.author.id})", inline=False
        )
        embed.add_field(name="Servidor", value=guild.name, inline=False)
        embed.set_footer(text="Enviado por mensaje privado al bot")

        print(f"Enviando mensaje de soporte: {message}")

        if support_channel:
            await support_channel.send(embed=embed)
            sended = True

        if sended:
            await ctx.send(MSG_SOPORTE_SENT)
        else:
            await ctx.send(MSG_SOPORTE_SERVER_NOT_DETERMINED)

    except Exception as e:
        print(f"[ERROR] {e}")
        await ctx.send(MSG_SOPORTE_ERROR)
        if log_channel:
            await log_channel.send(
                f"❗ Error en comando soporte por **{ctx.author.name}**: `{e}`"
            )




def identify_speaker_segments(transcript, participants):
    """Identifica segmentos de conversación y asigna participantes estimados"""
    if not transcript or not participants:
        return transcript
    
    # Dividir transcripción en segmentos por pausas o cambios de tema
    segments = []
    sentences = transcript.split('. ')
    
    current_speaker = 0
    for i, sentence in enumerate(sentences):
        if sentence.strip():
            # Alternar entre participantes cada cierto número de oraciones
            if i > 0 and i % 3 == 0:
                current_speaker = (current_speaker + 1) % len(participants)
            
            speaker_name = participants[current_speaker] if current_speaker < len(participants) else "Participante desconocido"
            segments.append(f"**{speaker_name}**: {sentence.strip()}")
    
    return '. '.join(segments) + '.'


async def generate_meeting_summary(transcript, participants, duration_minutes=0):
    """Genera un resumen de la reunión usando OpenAI"""
    if not openai_client or not transcript.strip():
        return None
    
    try:
        # Crear prompt para el resumen
        participants_list = ", ".join(participants) if participants else "Participantes no identificados"
        
        prompt = f"""
Analiza la siguiente transcripción de una reunión y genera un resumen profesional en español.

**Información de la reunión:**
- Participantes: {participants_list}
- Duración: {duration_minutes:.1f} minutos

**Transcripción:**
{transcript}

**Genera un resumen que incluya:**
1. **Resumen Ejecutivo**: Breve descripción de la reunión
2. **Puntos Clave Discutidos**: Los temas principales tratados
3. **Decisiones Tomadas**: Acuerdos o decisiones alcanzadas
4. **Acciones Pendientes**: Tareas o compromisos mencionados
5. **Próximos Pasos**: Acciones a realizar después de la reunión

Mantén el resumen conciso pero completo, usando un tono profesional.
"""
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente especializado en crear resúmenes de reuniones profesionales. Tu objetivo es extraer información clave y presentarla de manera estructurada y clara."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Error generando resumen con OpenAI: {e}")
        return None




async def recording_finished_callback(sink, channel, filename, guild_id, sink_type="Unknown", provider=None):
    """Callback que se ejecuta cuando termina la grabación"""
    provider = normalize_provider(provider)
    try:
        await channel.send(f"🔄 Procesando audio grabado (Sink: {sink_type})...")
        
        # Diferentes tipos de sink manejan archivos de manera diferente
        import glob
        
        print(f"Directorio de trabajo actual: {os.getcwd()}")
        print(f"Archivos en directorio: {os.listdir('.')}")
        print(f"Tipo de sink usado: {sink_type}")
        
        # Verificar si el sink tiene audio_data disponible
        if hasattr(sink, 'audio_data'):
            print(f"Sink audio_data keys: {list(sink.audio_data.keys()) if sink.audio_data else 'None'}")
            if sink.audio_data:
                print(f"Número de usuarios con audio: {len(sink.audio_data)}")
        
        # Buscar archivos según el tipo de sink
        if sink_type == "PCM":
            # PCMSink puede crear archivos .pcm
            generated_files = glob.glob("*.pcm") + glob.glob("*.wav")
        else:
            # WaveSink y otros crean archivos .wav
            generated_files = glob.glob("*.wav")
            
        print(f"Archivos de audio encontrados: {generated_files}")
        
        audio_files = []
        participants = []
        
        # Verificar si hay archivos de audio generados recientemente
        current_time = time.time()
        recent_files = []
        
        for file_path in generated_files:
            try:
                file_time = os.path.getmtime(file_path)
                age = current_time - file_time
                print(f"Archivo: {file_path}, edad: {age:.1f}s")
                # Archivos creados en los últimos 120 segundos (más tiempo)
                if age < 120:
                    recent_files.append(file_path)
            except Exception as e:
                print(f"Error verificando {file_path}: {e}")
                continue
        
        if recent_files:
            # Renombrar archivos para incluir información del usuario
            for i, file_path in enumerate(recent_files):
                new_name = f"{filename}_user_{i+1}.wav"
                try:
                    os.rename(file_path, new_name)
                    audio_files.append(new_name)
                    participants.append(f"Usuario {i+1}")
                    print(f"Archivo procesado: {file_path} -> {new_name}")
                except Exception as e:
                    print(f"Error renombrando {file_path}: {e}")
        
        # Si no encontramos archivos automáticos, intentar forzar la escritura del sink
        if not audio_files and hasattr(sink, 'audio_data') and sink.audio_data:
            print("Intentando forzar escritura de audio_data del sink...")
            
            for user_id, audio_data in sink.audio_data.items():
                try:
                    # Buscar el usuario por ID
                    user = None
                    for guild in bot.guilds:
                        user = guild.get_member(user_id)
                        if user:
                            break
                    
                    user_name = user.display_name if user else f"User_{user_id}"
                    participants.append(user_name)
                    
                    user_filename = f"{filename}_{user_name}_{user_id}.wav"
                    print(f"Intentando guardar audio para {user_name} en {user_filename}")
                    
                    # Verificar el estado del AudioData
                    print(f"AudioData para {user_name}: {type(audio_data)}")
                    if hasattr(audio_data, 'file'):
                        print(f"  - Tiene file: {audio_data.file}")
                    
                    # Intentar diferentes métodos de escritura
                    try:
                        audio_data.write(user_filename)
                        if os.path.exists(user_filename) and os.path.getsize(user_filename) > 0:
                            audio_files.append(user_filename)
                            print(f"  ✅ Audio guardado exitosamente para {user_name}")
                        else:
                            print(f"  ❌ Archivo creado pero está vacío para {user_name}")
                    except Exception as write_error:
                        print(f"  ❌ Error en write(): {write_error}")
                        
                        # Método alternativo: extraer datos directamente del BytesIO
                        if hasattr(audio_data, 'file') and audio_data.file:
                            try:
                                print(f"  🔄 Intentando extraer datos de BytesIO para {user_name}")
                                
                                # Obtener datos del BytesIO
                                audio_data.file.seek(0)  # Ir al inicio
                                raw_data = audio_data.file.read()
                                
                                if raw_data and len(raw_data) > 0:
                                    print(f"  📊 Datos extraídos: {len(raw_data)} bytes")
                                    
                                    # Guardar como archivo PCM primero
                                    pcm_filename = f"{filename}_{user_name}_{user_id}.pcm"
                                    with open(pcm_filename, 'wb') as pcm_file:
                                        pcm_file.write(raw_data)
                                    
                                    # Convertir PCM a WAV usando pydub
                                    try:
                                        from pydub import AudioSegment
                                        audio_segment = AudioSegment.from_raw(
                                            io.BytesIO(raw_data),
                                            sample_width=2,  # 16-bit
                                            frame_rate=48000,  # Discord rate
                                            channels=2  # Estéreo
                                        )
                                        audio_segment.export(user_filename, format="wav")
                                        audio_files.append(user_filename)
                                        print(f"  ✅ Audio extraído y convertido para {user_name}")
                                        
                                        # Limpiar archivo PCM temporal
                                        os.remove(pcm_filename)
                                        
                                    except Exception as convert_error:
                                        print(f"  ⚠️ Error convirtiendo estéreo, intentando mono: {convert_error}")
                                        try:
                                            # Intentar con mono
                                            from pydub import AudioSegment
                                            audio_segment = AudioSegment.from_raw(
                                                io.BytesIO(raw_data),
                                                sample_width=2,
                                                frame_rate=48000,
                                                channels=1  # Mono
                                            )
                                            audio_segment.export(user_filename, format="wav")
                                            audio_files.append(user_filename)
                                            print(f"  ✅ Audio extraído y convertido (mono) para {user_name}")
                                            os.remove(pcm_filename)
                                        except Exception as mono_error:
                                            print(f"  ❌ Error en conversión mono: {mono_error}")
                                            # Mantener archivo PCM como fallback
                                            audio_files.append(pcm_filename)
                                            print(f"  💾 Manteniendo archivo PCM para {user_name}")
                                else:
                                    print(f"  ❌ BytesIO está vacío para {user_name}")
                                    
                            except Exception as bytesio_error:
                                print(f"  ❌ Error extrayendo de BytesIO: {bytesio_error}")
                        
                except Exception as e:
                    print(f"Error general procesando usuario {user_id}: {e}")
                    continue
                    
        # Si aún no hay archivos, buscar por patrones comunes
        if not audio_files:
            print("Buscando archivos de audio con patrones comunes...")
            
            # Patrones que pueden usar diferentes sinks
            patterns = [
                f"{filename}*.wav",
                f"*{filename}*.wav", 
                f"*{int(time.time())}*.wav",
                "user_*.wav",
                "*_*.wav",
                "*.wav"  # Buscar CUALQUIER archivo WAV
            ]
            
            for pattern in patterns:
                found_files = glob.glob(pattern)
                print(f"Patrón '{pattern}' encontró: {found_files}")
                for file_path in found_files:
                    try:
                        file_time = os.path.getmtime(file_path)
                        age = current_time - file_time
                        print(f"  - {file_path}: {age:.1f}s de antigüedad")
                        # Archivos creados en los últimos 300 segundos (5 minutos)
                        if age < 300:
                            new_name = f"{filename}_found_{len(audio_files)}.wav"
                            os.rename(file_path, new_name)
                            audio_files.append(new_name)
                            participants.append(f"Participante {len(audio_files)}")
                            print(f"  ✅ Archivo encontrado: {file_path} -> {new_name}")
                    except Exception as e:
                        print(f"  ❌ Error procesando {file_path}: {e}")
                        continue
        
        # Como último recurso, crear un archivo de audio vacío para evitar errores
        if not audio_files:
            print("No se encontraron archivos de audio. Creando archivo de prueba...")
            try:
                # Crear un archivo de audio silencioso de 1 segundo como fallback
                from pydub import AudioSegment
                silence = AudioSegment.silent(duration=1000)  # 1 segundo de silencio
                test_file = f"{filename}_silence.wav"
                silence.export(test_file, format="wav")
                audio_files.append(test_file)
                participants.append("Sin audio detectado")
                await channel.send("⚠️ No se detectó audio en la grabación. Generando archivo de prueba.")
            except Exception as e:
                print(f"Error creando archivo de prueba: {e}")
        
        if not audio_files:
            await channel.send("⚠️ No se encontraron archivos de audio válidos.")
            return
        
        # Procesar archivos según el tipo
        if len(audio_files) == 1:
            final_audio_file = audio_files[0]
            
            # Si es archivo PCM, convertir a WAV
            if final_audio_file.endswith('.pcm'):
                try:
                    print(f"Convirtiendo archivo PCM a WAV: {final_audio_file}")
                    # Leer datos PCM y convertir a WAV
                    with open(final_audio_file, 'rb') as pcm_file:
                        pcm_data = pcm_file.read()
                    
                    # Crear AudioSegment desde datos PCM raw
                    from pydub import AudioSegment
                    audio_segment = AudioSegment.from_raw(
                        io.BytesIO(pcm_data),
                        sample_width=2,  # 16-bit
                        frame_rate=48000,  # Discord rate
                        channels=2  # Estéreo
                    )
                    
                    new_name = f"{filename}_converted.wav"
                    audio_segment.export(new_name, format="wav")
                    os.remove(final_audio_file)  # Limpiar archivo PCM
                    final_audio_file = new_name
                    print(f"Conversión exitosa: {new_name}")
                    
                except Exception as convert_error:
                    print(f"Error convirtiendo PCM: {convert_error}")
                    # Intentar con diferentes parámetros
                    try:
                        from pydub import AudioSegment
                        audio_segment = AudioSegment.from_raw(
                            io.BytesIO(pcm_data),
                            sample_width=2,
                            frame_rate=48000,
                            channels=1  # Mono
                        )
                        new_name = f"{filename}_converted_mono.wav"
                        audio_segment.export(new_name, format="wav")
                        os.remove(final_audio_file)
                        final_audio_file = new_name
                        print(f"Conversión mono exitosa: {new_name}")
                    except Exception as e2:
                        print(f"Error en conversión mono: {e2}")
                        await channel.send(f"⚠️ Error convirtiendo archivo PCM: {convert_error}")
                        return
            else:
                # Renombrar archivo WAV para mantener consistencia
                new_name = f"{filename}_combined.wav"
                os.rename(final_audio_file, new_name)
                final_audio_file = new_name
                
        else:
            # Combinar múltiples archivos de audio
            from pydub import AudioSegment
            combined_audio = AudioSegment.empty()
            
            for audio_file in audio_files:
                try:
                    from pydub import AudioSegment
                    if audio_file.endswith('.pcm'):
                        # Convertir PCM a AudioSegment
                        with open(audio_file, 'rb') as pcm_file:
                            pcm_data = pcm_file.read()
                        audio_segment = AudioSegment.from_raw(
                            io.BytesIO(pcm_data),
                            sample_width=2,
                            frame_rate=48000,
                            channels=2
                        )
                    else:
                        audio_segment = AudioSegment.from_wav(audio_file)
                    
                    combined_audio += audio_segment
                    # Limpiar archivo individual
                    os.remove(audio_file)
                except Exception as e:
                    print(f"Error procesando {audio_file}: {e}")
                    continue
            
            if len(combined_audio) == 0:
                await channel.send("⚠️ No se pudo procesar el audio grabado.")
                return
            
            # Guardar archivo combinado
            final_audio_file = f"{filename}_combined.wav"
            combined_audio.export(final_audio_file, format="wav")
        
        # Verificar que el archivo final existe
        if not os.path.exists(final_audio_file):
            await channel.send("⚠️ Error: No se pudo crear el archivo de audio final.")
            return
        
        await channel.send(f"🔄 Transcribiendo audio con {provider_label(provider)}...")

        # Calcular duración del audio final
        try:
            from pydub import AudioSegment
            audio_duration = AudioSegment.from_wav(final_audio_file).duration_seconds
        except:
            audio_duration = 0

        # Transcribir con el proveedor seleccionado
        try:
            transcript = await transcribe_audio_file(final_audio_file, provider=provider, language="es")
            transcription_available = True
        except Exception as transcription_error:
            transcript = ""
            transcription_available = False
            await channel.send(f"❌ Error transcribiendo con {provider_label(provider)}: {transcription_error}")
            print(f"Error de transcripción ({provider}): {transcription_error}")

        if transcription_available:
            if transcript:
                # Identificar segmentos de participantes
                segmented_transcript = identify_speaker_segments(transcript, participants)
                
                # Generar resumen con OpenAI
                await channel.send("🔄 Generando resumen de la reunión...")
                meeting_summary = await generate_meeting_summary(transcript, participants, audio_duration / 60)
                
                # Crear documento de transcripción mejorado
                doc_content = f"""# Transcripción de Conversación - Grabación Automática
**Archivo**: {filename}
**Fecha**: {time.strftime('%Y-%m-%d %H:%M:%S')}
**Participantes**: {', '.join(participants)}
**Duración**: {audio_duration:.1f} segundos

---

## Resumen de la Reunión

{meeting_summary if meeting_summary else "No se pudo generar el resumen automáticamente."}

---

## Transcripción con Participantes

{segmented_transcript}

---

## Transcripción Original

{transcript}

---

*Transcripción generada automáticamente usando {provider_label(provider)}*
*Resumen generado con OpenAI GPT-3.5-turbo*
*Audio capturado directamente del canal de Discord*
"""
                
                doc_filename = f"{filename}_transcripcion.md"
                with open(doc_filename, 'w', encoding='utf-8') as f:
                    f.write(doc_content)
                
                # Crear carpeta de grabaciones si no existe
                recordings_dir = os.path.join(os.getcwd(), "recordings")
                if not os.path.exists(recordings_dir):
                    os.makedirs(recordings_dir)
                
                # Mover archivos a la carpeta de grabaciones
                saved_doc_path = os.path.join(recordings_dir, doc_filename)
                saved_audio_path = os.path.join(recordings_dir, final_audio_file)
                
                # Mover archivos
                os.rename(doc_filename, saved_doc_path)
                os.rename(final_audio_file, saved_audio_path)
                
                await channel.send(f"✅ **Grabación y transcripción completadas**")
                await channel.send(f"📁 **Archivos guardados en:** `recordings/{doc_filename}` y `recordings/{final_audio_file}`")
                
                if log_channel:
                    await log_channel.send(f"📄 Grabación automática completada y guardada: {saved_doc_path}")
                
                # No eliminar archivos - mantenerlos en la carpeta recordings
            else:
                await channel.send("⚠️ No se pudo transcribir el audio (posiblemente silencio).")
                
                # Crear carpeta de grabaciones si no existe
                recordings_dir = os.path.join(os.getcwd(), "recordings")
                if not os.path.exists(recordings_dir):
                    os.makedirs(recordings_dir)
                
                # Mover archivo de audio a la carpeta de grabaciones
                saved_audio_path = os.path.join(recordings_dir, final_audio_file)
                os.rename(final_audio_file, saved_audio_path)
                
                await channel.send(f"📁 **Archivo de audio guardado en:** `recordings/{final_audio_file}` (sin transcripción)")
        else:
            # La transcripción falló; el error ya se notificó arriba. Guardamos el audio igualmente.
            # Crear carpeta de grabaciones si no existe
            recordings_dir = os.path.join(os.getcwd(), "recordings")
            if not os.path.exists(recordings_dir):
                os.makedirs(recordings_dir)
            
            # Mover archivo de audio a la carpeta de grabaciones
            saved_audio_path = os.path.join(recordings_dir, final_audio_file)
            os.rename(final_audio_file, saved_audio_path)
            
            await channel.send(f"📁 **Archivo de audio guardado en:** `recordings/{final_audio_file}` (sin transcripción)")
            
    except Exception as e:
        await channel.send(f"❌ Error procesando la grabación: {e}")
        print(f"Error en recording_finished_callback: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Limpiar datos de grabación
        if guild_id in recording_data:
            del recording_data[guild_id]


def resolve_target_guild(ctx):
    """Servidor objetivo para los comandos de voz.

    - Si el comando se escribe en un canal del servidor, devuelve ese servidor.
    - Si se escribe por mensaje privado (DM) y el bot está en un único servidor,
      devuelve ese servidor automáticamente.
    - Devuelve None si no se puede determinar (DM con el bot en varios servidores).
    """
    if ctx.guild is not None:
        return ctx.guild
    if len(bot.guilds) == 1:
        return bot.guilds[0]
    return None


async def stop_and_process_recording(guild, announce_channel=None):
    """Detiene la grabación activa de un servidor (si la hay) y procesa el audio.

    announce_channel: canal donde avisar y enviar el resultado. Si es None, se usa
    el canal desde donde se inició la grabación.
    Devuelve True si había una grabación que se ha detenido.
    """
    if guild.id not in recording_data:
        return False

    recording_info = recording_data[guild.id]
    voice_client = recording_info['voice_client']
    sink = recording_info['sink']
    sink_type = recording_info.get('sink_type', 'Unknown')
    filename = recording_info['filename']
    provider = recording_info.get('provider')
    channel = announce_channel or recording_info.get('channel')

    try:
        voice_client.stop_recording()
    except Exception as stop_error:
        print(f"Error deteniendo grabación: {stop_error}")
        if channel:
            await channel.send(f"⚠️ **Error deteniendo grabación**: {stop_error}")

    duration = time.time() - recording_info['start_time']
    if channel:
        await channel.send(f"⏹️ **Grabación detenida** — {filename}")
        await channel.send(f"⏱️ **Duración**: {duration:.1f} segundos")
        await channel.send(f"🔄 **Procesando audio con sink {sink_type}...**")
        await channel.send("⏳ *Esto puede tomar unos minutos dependiendo de la duración del audio*")

    # Procesar el audio (transcripción + resumen). Limpia recording_data al terminar.
    await asyncio.sleep(3)  # Dar tiempo a que se finalice la grabación
    await recording_finished_callback(sink, channel, filename, guild.id, sink_type, provider)
    return True


# Segundos que el bot espera estando solo antes de auto-desconectarse.
# Evita desconexiones por salidas momentáneas. 0 desactiva la auto-desconexión.
ALONE_DISCONNECT_GRACE = int(os.getenv("ALONE_DISCONNECT_GRACE_SECONDS", "60"))


@bot.event
async def on_voice_state_update(member, before, after):
    """Si el bot se queda solo en su canal de voz, detiene la grabación y se desconecta."""
    if ALONE_DISCONNECT_GRACE <= 0:
        return
    # Ignorar los cambios de estado del propio bot.
    if member.bot:
        return

    guild = member.guild
    if guild.id not in voice_clients:
        return

    bot_channel = voice_clients[guild.id].channel
    if bot_channel is None:
        return

    # Solo nos interesa cuando alguien SALE del canal del bot (incluye moverse a otro).
    if before.channel != bot_channel or after.channel == bot_channel:
        return

    # ¿Queda algún humano en el canal del bot?
    if any(not m.bot for m in bot_channel.members):
        return

    # El bot se ha quedado solo. Esperar un margen por si alguien vuelve enseguida.
    # Durante esta espera NO se toca voice_clients, así que un !grabar inmediato funciona.
    print(f"[voz] Bot solo en '{bot_channel.name}' ({guild.name}); espero {ALONE_DISCONNECT_GRACE}s antes de desconectar.")
    await asyncio.sleep(ALONE_DISCONNECT_GRACE)

    # Re-comprobar tras la espera: ¿sigo conectado al mismo canal y sigo solo?
    voice_client = voice_clients.get(guild.id)
    if voice_client is None or voice_client.channel is None:
        return  # Ya no estoy conectado (p. ej. !desconectar durante la espera).
    bot_channel = voice_client.channel
    if any(not m.bot for m in bot_channel.members):
        print(f"[voz] Alguien volvió a '{bot_channel.name}'; cancelo la auto-desconexión.")
        return

    # Sigo solo: avisar, parar la grabación (si la hay) y desconectar.
    was_recording = guild.id in recording_data
    announce = (recording_data.get(guild.id) or {}).get('channel') or log_channel
    if announce:
        if was_recording:
            await announce.send("👋 Me he quedado solo en el canal de voz. Detengo la grabación y me desconecto.")
        else:
            await announce.send("👋 Me he quedado solo en el canal de voz. Me desconecto.")

    await stop_and_process_recording(guild)

    voice_client = voice_clients.pop(guild.id, None)
    if voice_client is not None:
        try:
            await voice_client.disconnect()
        except Exception as e:
            print(f"Error al desconectar automáticamente: {e}")

    if log_channel:
        await log_channel.send(f"🔇 Bot desconectado automáticamente de '{bot_channel.name}' en {guild.name} (canal vacío).")


@bot.command(name="conectar")
async def join_voice(ctx, *, canal_nombre: str = None):
    if not await is_bot_admin(ctx):
        await ctx.send(MSG_ADMIN_REQUIRED)
        return

    target_guild = resolve_target_guild(ctx)
    if target_guild is None:
        await ctx.send("❌ No puedo determinar el servidor. Escribe el comando en un canal del servidor.")
        return

    # Determinar el canal de voz objetivo dentro de ese servidor.
    if canal_nombre:
        target_channel = discord.utils.find(
            lambda c: c.name.lower() == canal_nombre.lower(), target_guild.voice_channels
        )
        if target_channel is None:
            await ctx.send(f"❌ No se encontró un canal de voz llamado '{canal_nombre}' en este servidor.")
            return
    else:
        # Sin nombre: usar el canal de voz en el que está quien escribe.
        # get_member funciona tanto desde el servidor como desde un DM.
        member = target_guild.get_member(ctx.author.id)
        if member and member.voice and member.voice.channel:
            target_channel = member.voice.channel
        else:
            canales = "\n".join(f"• **{c.name}**" for c in target_guild.voice_channels) or "(no hay canales de voz)"
            await ctx.send(
                "❌ Entra a un canal de voz y vuelve a usar `!conectar`, o indica el nombre con `!conectar [canal]`.\n\n"
                f"**Canales de voz:**\n{canales}"
            )
            return

    if target_guild.id in voice_clients:
        current_channel = voice_clients[target_guild.id].channel
        await ctx.send(f"❌ Ya estoy conectado a **{current_channel.name}**. Usa `!desconectar` primero.")
        return

    try:
        voice_client = await target_channel.connect()
        voice_clients[target_guild.id] = voice_client
        await ctx.send(f"✅ Conectado al canal de voz: **{target_channel.name}**")

        if log_channel:
            await log_channel.send(f"🔊 Bot conectado al canal de voz '{target_channel.name}' en {target_guild.name} por {ctx.author.name}")

    except Exception as e:
        await ctx.send(f"❌ Error al conectar al canal de voz: {e}")


@bot.command(name="desconectar")
async def leave_voice(ctx):
    if not await is_bot_admin(ctx):
        await ctx.send(MSG_ADMIN_REQUIRED)
        return

    target_guild = resolve_target_guild(ctx)
    if target_guild is None:
        await ctx.send("❌ No puedo determinar el servidor. Escribe el comando en un canal del servidor.")
        return

    if target_guild.id not in voice_clients:
        await ctx.send("❌ No estoy conectado a ningún canal de voz en este servidor.")
        return

    voice_client = voice_clients[target_guild.id]
    channel_name = voice_client.channel.name if voice_client.channel else "Canal desconocido"

    if target_guild.id in recording_data:
        await ctx.send("⚠️ Grabación detenida automáticamente.")
        del recording_data[target_guild.id]

    await voice_client.disconnect()
    del voice_clients[target_guild.id]
    await ctx.send(f"✅ Desconectado del canal de voz **{channel_name}**.")

    if log_channel:
        await log_channel.send(f"🔇 Bot desconectado del canal de voz '{channel_name}' en {target_guild.name} por {ctx.author.name}")


@bot.command(name="grabar")
async def start_recording(ctx, proveedor: str = None, *, nombre_archivo: str = None):
    if not await is_bot_admin(ctx):
        await ctx.send(MSG_ADMIN_REQUIRED)
        return

    target_guild = resolve_target_guild(ctx)
    if target_guild is None:
        await ctx.send("❌ No puedo determinar el servidor. Escribe el comando en un canal del servidor.")
        return

    if target_guild.id not in voice_clients:
        await ctx.send("❌ No estoy conectado a ningún canal de voz. Usa `!conectar` primero.")
        return

    # El proveedor es opcional: si no es válido, forma parte del nombre del archivo.
    if proveedor and not is_valid_provider(proveedor):
        nombre_archivo = f"{proveedor} {nombre_archivo}".strip() if nombre_archivo else proveedor
        proveedor = None
    proveedor = normalize_provider(proveedor)

    if target_guild.id in recording_data:
        await ctx.send("❌ Ya hay una grabación en progreso en este servidor.")
        return

    if nombre_archivo is None:
        timestamp = int(time.time())
        nombre_archivo = f"grabacion_{timestamp}"
    
    try:
        voice_client = voice_clients[target_guild.id]
        
        # Intentar con diferentes tipos de sink para mayor compatibilidad
        try:
            # Intentar primero con PCMSink que es más básico
            sink = discord.sinks.PCMSink()
            sink_type = "PCM"
        except Exception as e:
            print(f"No se pudo crear PCMSink: {e}, intentando WaveSink")
            try:
                sink = discord.sinks.WaveSink()
                sink_type = "WAV"
            except Exception as e2:
                print(f"No se pudo crear WaveSink: {e2}, usando sink básico")
                # Crear un sink personalizado más simple
                sink = discord.sinks.Sink()
                sink_type = "Basic"
        
        print(f"Usando sink tipo: {sink_type}")
        
        # Crear un callback async simple que maneja errores
        async def simple_callback(sink, exc=None):
            if exc:
                print(f"Error en callback de grabación: {exc}")
            # No hacer más nada - manejaremos el procesamiento manualmente en !parar
            pass
            
        # Iniciar la grabación con manejo de errores
        try:
            voice_client.start_recording(sink, simple_callback)
            await ctx.send(f"✅ Grabación iniciada con sink {sink_type}")
        except Exception as record_error:
            await ctx.send(f"❌ Error iniciando grabación: {record_error}")
            print(f"Error detallado al iniciar grabación: {record_error}")
            return
        
        recording_data[target_guild.id] = {
            'sink': sink,
            'sink_type': sink_type,
            'filename': nombre_archivo,
            'start_time': time.time(),
            'channel': ctx.channel,
            'guild': target_guild,
            'voice_client': voice_client,
            'provider': proveedor,
        }

        channel_name = voice_client.channel.name
        await ctx.send(f"🔴 **Grabación AUTOMÁTICA iniciada**: {nombre_archivo}")
        await ctx.send(f"📍 **Canal**: {channel_name}")
        await ctx.send(f"🗣️ **Transcripción**: {provider_label(proveedor)}")
        await ctx.send("✅ **El bot está grabando automáticamente todo el audio del canal**")
        await ctx.send("Usa `!parar` para detener la grabación y obtener la transcripción.")
        await ctx.send("🎙️ **Habla normalmente** - El bot captura automáticamente todas las voces del canal.")
        
        if log_channel:
            await log_channel.send(f"🎙️ Grabación automática iniciada por {ctx.author.name}: {nombre_archivo} en {target_guild.name}")
    
    except Exception as e:
        await ctx.send(f"❌ Error al iniciar la grabación: {e}")
        print(f"Error detallado: {e}")


@bot.command(name="parar")
async def stop_recording(ctx):
    if not await is_bot_admin(ctx):
        await ctx.send(MSG_ADMIN_REQUIRED)
        return

    target_guild = resolve_target_guild(ctx)
    if target_guild is None:
        await ctx.send("❌ No puedo determinar el servidor. Escribe el comando en un canal del servidor.")
        return

    if target_guild.id not in recording_data:
        await ctx.send("❌ No hay ninguna grabación en progreso en este servidor.")
        return

    await stop_and_process_recording(target_guild, announce_channel=ctx.channel)

    if log_channel:
        await log_channel.send(f"⏹️ Grabación detenida por {ctx.author.name} en {target_guild.name}.")


@bot.command(name="transcribir")
async def transcribe_audio(ctx, proveedor: str = None, *, nombre_salida: str = None):
    if not await is_bot_admin(ctx):
        await ctx.send(MSG_ADMIN_REQUIRED)
        return

    if not ctx.message.attachments:
        await ctx.send("❌ Por favor adjunta un archivo de audio (WAV, MP3, M4A, etc.)")
        return

    # El primer argumento es opcional: si no es un proveedor válido, es el nombre de salida.
    if proveedor and not is_valid_provider(proveedor):
        nombre_salida = f"{proveedor} {nombre_salida}".strip() if nombre_salida else proveedor
        proveedor = None
    proveedor = normalize_provider(proveedor)
    
    attachment = ctx.message.attachments[0]
    
    if not any(attachment.filename.lower().endswith(ext) for ext in ['.wav', '.mp3', '.m4a', '.ogg', '.flac']):
        await ctx.send("❌ Formato de archivo no soportado. Usa: WAV, MP3, M4A, OGG, FLAC")
        return
    
    if nombre_salida is None:
        nombre_salida = f"transcripcion_{int(time.time())}"
    
    try:
        await ctx.send("🔄 Descargando archivo de audio...")
        
        audio_file = f"temp_{attachment.filename}"
        await attachment.save(audio_file)

        await ctx.send(f"🔄 Transcribiendo audio con {provider_label(proveedor)}... Esto puede tomar varios minutos.")

        try:
            transcript = await transcribe_audio_file(audio_file, provider=proveedor, language="es")
            transcription_available = True
        except Exception as transcription_error:
            transcript = ""
            transcription_available = False
            await ctx.send(f"❌ Error transcribiendo con {provider_label(proveedor)}: {transcription_error}")
            print(f"Error de transcripción ({proveedor}): {transcription_error}")

        if transcription_available:
            if transcript:
                # Generar resumen con OpenAI
                await ctx.send("🔄 Generando resumen del audio...")
                meeting_summary = await generate_meeting_summary(transcript, [], 0)
                
                doc_content = f"""# Transcripción de Audio
**Archivo original**: {attachment.filename}
**Fecha de transcripción**: {time.strftime('%Y-%m-%d %H:%M:%S')}
**Procesado por**: {ctx.author.display_name}
**Tamaño del archivo**: {attachment.size / 1024 / 1024:.2f} MB

---

## Resumen del Audio

{meeting_summary if meeting_summary else "No se pudo generar el resumen automáticamente."}

---

## Transcripción

{transcript}

---

*Transcripción generada automáticamente usando {provider_label(proveedor)}*
*Resumen generado con OpenAI GPT-3.5-turbo*
"""

                doc_filename = f"{nombre_salida}.md"
                with open(doc_filename, 'w', encoding='utf-8') as f:
                    f.write(doc_content)
                
                # Crear carpeta de grabaciones si no existe
                recordings_dir = os.path.join(os.getcwd(), "recordings")
                if not os.path.exists(recordings_dir):
                    os.makedirs(recordings_dir)
                
                # Mover archivo de transcripción a la carpeta de grabaciones
                saved_doc_path = os.path.join(recordings_dir, doc_filename)
                os.rename(doc_filename, saved_doc_path)
                
                await ctx.send("✅ **Transcripción completada**")
                await ctx.send(f"📁 **Archivo guardado en:** `recordings/{doc_filename}`")
                
                if log_channel:
                    await log_channel.send(f"📄 Transcripción generada por {ctx.author.name} y guardada: {saved_doc_path}")
            else:
                await ctx.send("⚠️ No se pudo transcribir el audio (posiblemente silencio o audio no reconocible).")
        # Si la transcripción falló, el error ya se notificó arriba.

        os.remove(audio_file)
        
    except Exception as e:
        await ctx.send(f"❌ Error procesando el archivo: {e}")
        print(f"Error en transcribe_audio: {e}")
        
        try:
            os.remove(audio_file)
        except:
            pass


@bot.command(name="estado")
async def recording_status(ctx):
    """Muestra el estado actual de conexiones y grabaciones"""
    if not await is_bot_admin(ctx):
        await ctx.send(MSG_ADMIN_REQUIRED)
        return
    
    embed = discord.Embed(
        title="🤖 Estado del Bot de Grabación",
        color=0x00ff00 if voice_clients else 0xff0000
    )
    
    # Estado de conexiones de voz
    if voice_clients:
        connections = []
        for guild_id, voice_client in voice_clients.items():
            guild = bot.get_guild(guild_id)
            if guild and voice_client.channel:
                connections.append(f"🔊 **{guild.name}** - Canal: {voice_client.channel.name}")
        
        if connections:
            embed.add_field(
                name="Conexiones de Voz Activas",
                value="\n".join(connections),
                inline=False
            )
    else:
        embed.add_field(
            name="Conexiones de Voz",
            value="❌ No conectado a ningún canal",
            inline=False
        )
    
    # Estado de grabaciones
    if recording_data:
        recordings = []
        for guild_id, rec_info in recording_data.items():
            guild = bot.get_guild(guild_id)
            if guild:
                duration = time.time() - rec_info['start_time']
                recordings.append(f"🔴 **{guild.name}** - {rec_info['filename']} ({duration:.1f}s)")
        
        if recordings:
            embed.add_field(
                name="Grabaciones en Progreso",
                value="\n".join(recordings),
                inline=False
            )
    else:
        embed.add_field(
            name="Grabaciones",
            value="⚫ No hay grabaciones activas",
            inline=False
        )
    
    # Estado de la transcripción
    openai_status = "✅" if OPENAI_API_KEY else "❌"
    mistral_status = "✅" if os.getenv("MISTRAL_API_KEY") else "❌"
    embed.add_field(
        name="Transcripción",
        value=(
            f"🔵 Proveedor por defecto: **{provider_label(DEFAULT_TRANSCRIPTION_PROVIDER)}**\n"
            f"{openai_status} OpenAI (gpt-4o-transcribe)\n"
            f"{mistral_status} Mistral Voxtral\n"
            f"✅ Whisper local"
        ),
        inline=False
    )
    
    embed.set_footer(text=f"Bot conectado como {bot.user.name}")
    
    await ctx.send(embed=embed)


if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("Bot detenido por el usuario")
    finally:
        # Limpiar conexiones de voz
        for vc in voice_clients.values():
            if vc.is_connected():
                asyncio.run(vc.disconnect())
        print("Conexiones de voz cerradas")
