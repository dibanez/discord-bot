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
import whisper
from pydub import AudioSegment
import io

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
GOOGLE_SHEET_TAB = os.getenv("GOOGLE_SHEET_TAB")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))

# --- Verification Settings ---
VERIFICATION_MAX_ATTEMPTS = int(os.getenv("VERIFICATION_MAX_ATTEMPTS", 3))

# --- Configurable Messages ---
# On Member Join
MSG_MEMBER_JOIN_WELCOME = os.getenv(
    "MSG_MEMBER_JOIN_WELCOME",
    "👋 ¡Bienvenido al servidor de ANFAIA!\n\n"
    "Para poder acceder al resto del servidor, por favor **responde a este mensaje escribiendo únicamente la clave** que se te ha facilitado con la invitación.\n"
    "🔑 *Es importante que la pongas tal cual la recibiste, sin modificar nada.*\n\n"
    "Si tienes algún problema con la clave o necesitas ayuda, **escribe el comando `!soporte` seguido de tu mensaje aquí mismo, en este chat privado con el bot**.\n\n"
    "Por ejemplo:\n"
    "`!soporte No he recibido la clave y no puedo acceder al servidor.`\n\n"
    "Un administrador revisará tu mensaje y te responderá lo antes posible.\n\n"
    "¡Gracias por unirte a la Asociación Nacional Faro para la Aceleración de la Inteligencia Artificial!",
)
MSG_MEMBER_JOIN_TIMEOUT = os.getenv(
    "MSG_MEMBER_JOIN_TIMEOUT",
    "⏰ Se acabó el tiempo para introducir la clave. Si necesitas ayuda, usa `!soporte` o contacta a un administrador.",
)
MSG_MEMBER_JOIN_ERROR = os.getenv(
    "MSG_MEMBER_JOIN_ERROR", "⚠️ Hubo un error al procesar tu verificación."
)
MSG_VERIFY_RETRY_PROMPT = os.getenv(
    "MSG_VERIFY_RETRY_PROMPT",
    "❌ Clave incorrecta. Te quedan {attempts_left} intento(s). Por favor, inténtalo de nuevo:",
)
MSG_VERIFY_NO_ATTEMPTS_LEFT = os.getenv(
    "MSG_VERIFY_NO_ATTEMPTS_LEFT",
    "❌ Has agotado todos tus intentos. Por favor, contacta con un administrador o usa el comando `!soporte` si necesitas ayuda.",
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
whisper_model = None

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
    global whisper_model
    guild = discord.utils.get(bot.guilds)
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    support_channel = bot.get_channel(SUPPORT_CHANNEL_ID)
    
    try:
        whisper_model = whisper.load_model("base")
        print("✅ Modelo Whisper cargado correctamente")
    except Exception as e:
        print(f"⚠️ Error cargando modelo Whisper: {e}")
    
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

            def check(m):
                return m.author == member and isinstance(m.channel, discord.DMChannel)

            try:
                # The prompt to enter the key is the welcome message (first attempt)
                # or the retry message (subsequent attempts).
                msg = await bot.wait_for(
                    "message", check=check, timeout=540.0
                )  # 540 seconds timeout
            except asyncio.TimeoutError:
                # Using existing timeout message, but log attempt context
                timeout_message_to_send = (
                    MSG_MEMBER_JOIN_TIMEOUT  # Default timeout message
                )
                if (
                    VERIFICATION_MAX_ATTEMPTS - attempts_left > 0
                ):  # Not the first attempt
                    timeout_message_to_send = (
                        MSG_MEMBER_JOIN_TIMEOUT + " (Intento agotado)"
                    )

                try:
                    await member.send(timeout_message_to_send)
                except (DiscordForbiddenError, DiscordHTTPException):
                    pass  # User might have blocked/left

                if log_channel:
                    await log_channel.send(
                        f"⏰ **{member.name} ({member.id})** no introdujo la clave a tiempo (intento {VERIFICATION_MAX_ATTEMPTS - attempts_left + 1})."
                    )
                return  # End verification for this user

            key_provided = msg.content.strip()
            # Pass the current attempt number for logging purposes, if needed by _verify_member_key
            verification_successful = await _verify_member_key(
                member, key_provided, sheet, log_channel
            )

            if verification_successful:
                # _verify_member_key handles success messages to user and log
                return  # Exit on_member_join successfully

            # Verification failed for this attempt (key incorrect or other handled issue in _verify_member_key)
            attempts_left -= 1
            if attempts_left > 0:
                try:
                    await member.send(
                        MSG_VERIFY_RETRY_PROMPT.format(attempts_left=attempts_left)
                    )
                except (DiscordForbiddenError, DiscordHTTPException):
                    if log_channel:
                        await log_channel.send(
                            f"⚠️ No se pudo enviar DM de reintento a {member.mention} ({member.id}). DMs desactivados/bloqueado."
                        )
                    return  # Cannot continue if we can't prompt for retry
            else:
                # All attempts used up
                try:
                    await member.send(MSG_VERIFY_NO_ATTEMPTS_LEFT)
                except (DiscordForbiddenError, DiscordHTTPException):
                    if log_channel:
                        await log_channel.send(
                            f"⚠️ No se pudo enviar DM de 'sin intentos' a {member.mention} ({member.id}). DMs desactivados/bloqueado."
                        )

                if log_channel:
                    await log_channel.send(
                        f"❌ **{member.name} ({member.id})** falló la verificación después de {VERIFICATION_MAX_ATTEMPTS} intentos."
                    )
                return  # End verification

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




async def recording_finished_callback(sink, channel, filename, guild_id, sink_type="Unknown"):
    """Callback que se ejecuta cuando termina la grabación"""
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
        
        await channel.send("🔄 Transcribiendo audio...")
        
        # Calcular duración del audio final
        try:
            from pydub import AudioSegment
            audio_duration = AudioSegment.from_wav(final_audio_file).duration_seconds
        except:
            audio_duration = 0
        
        # Transcribir con Whisper
        if whisper_model:
            result = whisper_model.transcribe(final_audio_file, language="es")
            transcript = result["text"].strip()
            
            if transcript:
                # Crear documento de transcripción
                doc_content = f"""# Transcripción de Conversación - Grabación Automática
**Archivo**: {filename}
**Fecha**: {time.strftime('%Y-%m-%d %H:%M:%S')}
**Participantes**: {', '.join(participants)}
**Duración**: {audio_duration:.1f} segundos

---

## Transcripción

{transcript}

---

*Transcripción generada automáticamente usando Whisper AI*
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
            await channel.send("❌ Modelo de transcripción no disponible.")
            
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


@bot.command(name="conectar")
async def join_voice(ctx, *, canal_nombre: str = None):
    if not await is_bot_admin(ctx):
        await ctx.send(MSG_ADMIN_REQUIRED)
        return
    
    # Si no se especifica canal, mostrar ayuda
    if canal_nombre is None:
        # Listar canales de voz disponibles
        available_channels = []
        for guild in bot.guilds:
            for channel in guild.voice_channels:
                available_channels.append(f"• **{channel.name}** (Servidor: {guild.name})")
        
        if available_channels:
            channels_text = "\n".join(available_channels)
            await ctx.send(f"❌ Especifica el nombre del canal de voz.\n\n**Canales disponibles:**\n{channels_text}\n\n**Uso:** `!conectar [nombre del canal]`")
        else:
            await ctx.send("❌ No hay canales de voz disponibles en los servidores.")
        return
    
    # Buscar el canal por nombre en todos los servidores
    target_channel = None
    target_guild = None
    
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            if channel.name.lower() == canal_nombre.lower():
                target_channel = channel
                target_guild = guild
                break
        if target_channel:
            break
    
    if target_channel is None:
        await ctx.send(f"❌ No se encontró un canal de voz llamado '{canal_nombre}'.")
        return
    
    if target_guild.id in voice_clients:
        current_channel = voice_clients[target_guild.id].channel
        await ctx.send(f"❌ Ya estoy conectado a un canal de voz en {target_guild.name}: **{current_channel.name}**")
        return
    
    try:
        voice_client = await target_channel.connect()
        voice_clients[target_guild.id] = voice_client
        await ctx.send(f"✅ Conectado al canal de voz: **{target_channel.name}** en el servidor **{target_guild.name}**")
        
        if log_channel:
            await log_channel.send(f"🔊 Bot conectado al canal de voz '{target_channel.name}' en {target_guild.name} por {ctx.author.name}")
    
    except Exception as e:
        await ctx.send(f"❌ Error al conectar al canal de voz: {e}")


@bot.command(name="desconectar")
async def leave_voice(ctx, *, servidor_nombre: str = None):
    if not await is_bot_admin(ctx):
        await ctx.send(MSG_ADMIN_REQUIRED)
        return
    
    if not voice_clients:
        await ctx.send("❌ No estoy conectado a ningún canal de voz.")
        return
    
    # Si no se especifica servidor, mostrar donde está conectado
    if servidor_nombre is None:
        connected_servers = []
        for guild_id, voice_client in voice_clients.items():
            guild = bot.get_guild(guild_id)
            if guild and voice_client.channel:
                connected_servers.append(f"• **{guild.name}** - Canal: {voice_client.channel.name}")
        
        if connected_servers:
            servers_text = "\n".join(connected_servers)
            await ctx.send(f"❌ Especifica el servidor del cual desconectar.\n\n**Conectado en:**\n{servers_text}\n\n**Uso:** `!desconectar [nombre del servidor]`")
        else:
            await ctx.send("❌ No estoy conectado a ningún canal de voz actualmente.")
        return
    
    # Buscar el servidor por nombre
    target_guild = None
    for guild in bot.guilds:
        if guild.name.lower() == servidor_nombre.lower():
            target_guild = guild
            break
    
    if target_guild is None:
        await ctx.send(f"❌ No se encontró un servidor llamado '{servidor_nombre}'.")
        return
    
    if target_guild.id not in voice_clients:
        await ctx.send(f"❌ No estoy conectado a ningún canal de voz en el servidor '{target_guild.name}'.")
        return
    
    voice_client = voice_clients[target_guild.id]
    channel_name = voice_client.channel.name if voice_client.channel else "Canal desconocido"
    
    if target_guild.id in recording_data:
        await ctx.send("⚠️ Grabación detenida automáticamente.")
        del recording_data[target_guild.id]
    
    await voice_client.disconnect()
    del voice_clients[target_guild.id]
    await ctx.send(f"✅ Desconectado del canal de voz **{channel_name}** en el servidor **{target_guild.name}**.")
    
    if log_channel:
        await log_channel.send(f"🔇 Bot desconectado del canal de voz '{channel_name}' en {target_guild.name} por {ctx.author.name}")


@bot.command(name="grabar")
async def start_recording(ctx, servidor_nombre: str = None, *, nombre_archivo: str = None):
    if not await is_bot_admin(ctx):
        await ctx.send(MSG_ADMIN_REQUIRED)
        return
    
    if not voice_clients:
        await ctx.send("❌ No estoy conectado a ningún canal de voz. Usa `!conectar [canal]` primero.")
        return
    
    # Si no se especifica servidor, mostrar opciones
    if servidor_nombre is None:
        connected_servers = []
        for guild_id, voice_client in voice_clients.items():
            guild = bot.get_guild(guild_id)
            if guild and voice_client.channel:
                connected_servers.append(f"• **{guild.name}** - Canal: {voice_client.channel.name}")
        
        if connected_servers:
            servers_text = "\n".join(connected_servers)
            await ctx.send(f"❌ Especifica el servidor donde grabar.\n\n**Conectado en:**\n{servers_text}\n\n**Uso:** `!grabar [servidor] [nombre archivo opcional]`")
        return
    
    # Buscar el servidor por nombre
    target_guild = None
    for guild in bot.guilds:
        if guild.name.lower() == servidor_nombre.lower():
            target_guild = guild
            break
    
    if target_guild is None:
        await ctx.send(f"❌ No se encontró un servidor llamado '{servidor_nombre}'.")
        return
    
    if target_guild.id not in voice_clients:
        await ctx.send(f"❌ No estoy conectado a ningún canal de voz en el servidor '{target_guild.name}'. Usa `!conectar [canal]` primero.")
        return
    
    if target_guild.id in recording_data:
        await ctx.send(f"❌ Ya hay una grabación en progreso en el servidor '{target_guild.name}'.")
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
            'voice_client': voice_client
        }
        
        channel_name = voice_client.channel.name
        await ctx.send(f"🔴 **Grabación AUTOMÁTICA iniciada**: {nombre_archivo}")
        await ctx.send(f"📍 **Servidor**: {target_guild.name} - Canal: {channel_name}")
        await ctx.send("✅ **El bot está grabando automáticamente todo el audio del canal**")
        await ctx.send(f"Usa `!parar {target_guild.name}` para detener la grabación y obtener la transcripción.")
        await ctx.send("🎙️ **Habla normalmente** - El bot captura automáticamente todas las voces del canal.")
        
        if log_channel:
            await log_channel.send(f"🎙️ Grabación automática iniciada por {ctx.author.name}: {nombre_archivo} en {target_guild.name}")
    
    except Exception as e:
        await ctx.send(f"❌ Error al iniciar la grabación: {e}")
        print(f"Error detallado: {e}")


@bot.command(name="parar")
async def stop_recording(ctx, *, servidor_nombre: str = None):
    if not await is_bot_admin(ctx):
        await ctx.send(MSG_ADMIN_REQUIRED)
        return
    
    if not recording_data:
        await ctx.send("❌ No hay ninguna grabación en progreso.")
        return
    
    # Si no se especifica servidor, mostrar grabaciones activas
    if servidor_nombre is None:
        active_recordings = []
        for guild_id, rec_info in recording_data.items():
            guild = bot.get_guild(guild_id)
            if guild:
                active_recordings.append(f"• **{guild.name}** - Archivo: {rec_info['filename']}")
        
        if active_recordings:
            recordings_text = "\n".join(active_recordings)
            await ctx.send(f"❌ Especifica el servidor donde parar la grabación.\n\n**Grabaciones activas:**\n{recordings_text}\n\n**Uso:** `!parar [servidor]`")
        return
    
    # Buscar el servidor por nombre
    target_guild = None
    for guild in bot.guilds:
        if guild.name.lower() == servidor_nombre.lower():
            target_guild = guild
            break
    
    if target_guild is None:
        await ctx.send(f"❌ No se encontró un servidor llamado '{servidor_nombre}'.")
        return
    
    if target_guild.id not in recording_data:
        await ctx.send(f"❌ No hay ninguna grabación en progreso en el servidor '{target_guild.name}'.")
        return
    
    recording_info = recording_data[target_guild.id]
    voice_client = recording_info['voice_client']
    sink = recording_info['sink']
    sink_type = recording_info.get('sink_type', 'Unknown')
    filename = recording_info['filename']
    
    # Detener la grabación real
    try:
        voice_client.stop_recording()
        await ctx.send(f"⏹️ **Grabación automática detenida** en {target_guild.name}")
    except Exception as stop_error:
        await ctx.send(f"⚠️ **Error deteniendo grabación**: {stop_error}")
        print(f"Error deteniendo grabación: {stop_error}")
    
    duration = time.time() - recording_info['start_time']
    await ctx.send(f"📊 **Archivo**: {filename}")
    await ctx.send(f"⏱️ **Duración**: {duration:.1f} segundos")
    await ctx.send(f"🔄 **Procesando audio con sink {sink_type}...**")
    await ctx.send("⏳ *Esto puede tomar unos minutos dependiendo de la duración del audio*")
    
    # Procesar el audio directamente aquí
    await asyncio.sleep(3)  # Dar más tiempo a que se finalice la grabación
    await recording_finished_callback(sink, ctx.channel, filename, target_guild.id, sink_type)
    
    if log_channel:
        await log_channel.send(f"⏹️ Grabación automática detenida por {ctx.author.name} en {target_guild.name}. Duración: {duration:.1f}s")


@bot.command(name="transcribir")
async def transcribe_audio(ctx, *, nombre_salida: str = None):
    if not await is_bot_admin(ctx):
        await ctx.send(MSG_ADMIN_REQUIRED)
        return
    
    if not ctx.message.attachments:
        await ctx.send("❌ Por favor adjunta un archivo de audio (WAV, MP3, M4A, etc.)")
        return
    
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
        
        await ctx.send("🔄 Transcribiendo audio... Esto puede tomar varios minutos.")
        
        if whisper_model:
            result = whisper_model.transcribe(audio_file, language="es")
            transcript = result["text"].strip()
            
            if transcript:
                doc_content = f"""# Transcripción de Audio
**Archivo original**: {attachment.filename}
**Fecha de transcripción**: {time.strftime('%Y-%m-%d %H:%M:%S')}
**Procesado por**: {ctx.author.display_name}
**Tamaño del archivo**: {attachment.size / 1024 / 1024:.2f} MB

---

## Transcripción

{transcript}

---

*Transcripción generada automáticamente usando Whisper AI*
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
        else:
            await ctx.send("❌ Error: Modelo de transcripción no disponible.")
        
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
    
    # Estado del modelo Whisper
    whisper_status = "✅ Disponible" if whisper_model else "❌ No disponible"
    embed.add_field(
        name="Transcripción (Whisper)",
        value=whisper_status,
        inline=True
    )
    
    embed.set_footer(text=f"Bot conectado como {bot.user.name}")
    
    await ctx.send(embed=embed)


bot.run(DISCORD_TOKEN)
