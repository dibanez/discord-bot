import discord
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from discord.ext import commands
from discord.ext.commands import has_permissions
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio  # for TimeoutError
import gspread
from gspread.exceptions import (
    SpreadsheetNotFound,
    WorksheetNotFound,
    APIError as GSpreadAPIError,
)
import discord  # Ensure discord is imported for its exceptions
from discord.errors import (
    Forbidden as DiscordForbiddenError,
    HTTPException as DiscordHTTPException,
)

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
bot = commands.Bot(command_prefix="!", intents=intents)

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
    guild = discord.utils.get(bot.guilds)
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    support_channel = bot.get_channel(SUPPORT_CHANNEL_ID)
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


bot.run(DISCORD_TOKEN)
