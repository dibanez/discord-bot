import discord
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from discord.ext import commands
from discord.ext.commands import has_permissions
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
GOOGLE_SHEET_TAB = os.getenv("GOOGLE_SHEET_TAB")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID"))


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


@bot.event
async def on_member_join(member):
    try:
        await member.send(
            "👋 ¡Bienvenido al servidor de ANFAIA!\n\n"
            "Para poder acceder al resto del servidor, por favor **responde a este mensaje escribiendo únicamente la clave** que se te ha facilitado con la invitación.\n"
            "🔑 *Es importante que la pongas tal cual la recibiste, sin modificar nada.*\n\n"
            "Si tienes algún problema con la clave o necesitas ayuda, **escribe el comando `!soporte` seguido de tu mensaje aquí mismo, en este chat privado con el bot**.\n\n"
            "Por ejemplo:\n"
            "`!soporte No he recibido la clave y no puedo acceder al servidor.`\n\n"
            "Un administrador revisará tu mensaje y te responderá lo antes posible.\n\n"
            "¡Gracias por unirte a la Asociación Nacional Faro para la Aceleración de la Inteligencia Artificial!"
        )

        def check(m):
            return m.author == member and isinstance(m.channel, discord.DMChannel)

        msg = await bot.wait_for("message", check=check, timeout=120)

        rows = sheet.get_all_records()
        for row in rows:
            if row["Clave"] == msg.content.strip():
                nombre = row["Nombre Discord"]
                rol_nombre = row["Rol Asignado"]

                await member.edit(nick=nombre)
                role = discord.utils.get(member.guild.roles, name=rol_nombre)
                if role:
                    await member.add_roles(role)
                    await member.send(
                        f"✅ Verificado. Se te ha asignado el rol `{rol_nombre}`."
                    )
                    if log_channel:
                        await log_channel.send(
                            f"✅ **{member.name}** verificado como `{nombre}` y asignado el rol `{rol_nombre}`."
                        )
                else:
                    await member.send(
                        f"⚠️ Clave correcta, pero no se encontró el rol `{rol_nombre}`."
                    )
                    if log_channel:
                        await log_channel.send(
                            f"⚠️ **{member.name}** tenía clave válida, pero rol `{rol_nombre}` no encontrado."
                        )
                return

        await member.send(
            "❌ Clave incorrecta. Contacta con un admin si crees que es un error."
        )
        if log_channel:
            await log_channel.send(
                f"❌ **{member.name}** falló en la verificación con clave inválida."
            )

    except Exception as e:
        print(f"[ERROR] {e}")
        if log_channel:
            await log_channel.send(f"❗ Error verificando a **{member.name}**: `{e}`")
        try:
            await member.send("⚠️ Hubo un error al procesar tu verificación.")
        except:
            pass


@bot.command(name="testclave")
async def test_clave(ctx, password: str = None):

    is_admin = False
    if isinstance(ctx.channel, discord.DMChannel):
        for guild in bot.guilds:
            member = guild.get_member(ctx.author.id)
            if member and member.guild_permissions.administrator:
                is_admin = True
                break
    else:
        is_admin = ctx.author.guild_permissions.administrator

    if not is_admin:
        await ctx.send("❌ Necesitas permisos de Administrador para usar este comando.")
        return

    if password is None:
        await ctx.send("❌ Uso: `!testclave [clave]`")
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
            await ctx.send("❌ Clave no encontrada en la hoja de cálculo.")

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
        await ctx.send(f"❗ Error al probar la clave: `{e}`")

        if log_channel:
            await log_channel.send(
                f"❗ Error en comando testclave por **{ctx.author.name}**: `{e}`"
            )


@bot.command(name="soporte")
async def support(ctx, *, message: str = None):
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("❌ Este comando solo se puede usar por mensaje privado al bot.")
        return

    if message is None:
        await ctx.send("❌ Debes escribir un mensaje. Uso: `!soporte [mensaje]`")
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
            await ctx.send(
                "✅ Tu mensaje ha sido enviado al equipo de soporte. Te responderán pronto."
            )
        else:
            await ctx.send(
                "⚠️ No se ha podido determinar tu servidor. Contacta con un administrador."
            )

    except Exception as e:
        print(f"[ERROR] {e}")
        await ctx.send("❗ Hubo un error al enviar tu solicitud. Inténtalo más tarde.")
        if log_channel:
            await log_channel.send(
                f"❗ Error en comando soporte por **{ctx.author.name}**: `{e}`"
            )


bot.run(DISCORD_TOKEN)
