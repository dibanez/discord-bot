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


intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_PATH, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).worksheet(GOOGLE_SHEET_TAB)


@bot.event
async def on_ready():
    global log_channel
    guild = discord.utils.get(bot.guilds)
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    print(f"✅ Bot listo como: {bot.user.name}")
    if log_channel:
        await log_channel.send("🟢 Bot iniciado correctamente.")

@bot.event
async def on_member_join(member):
    try:
        await member.send("👋 ¡Bienvenido! Por favor, introduce tu clave para verificar tu acceso:")

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
                    await member.send(f"✅ Verificado. Se te ha asignado el rol `{rol_nombre}`.")
                    if log_channel:
                        await log_channel.send(f"✅ **{member.name}** verificado como `{nombre}` y asignado el rol `{rol_nombre}`.")
                else:
                    await member.send(f"⚠️ Clave correcta, pero no se encontró el rol `{rol_nombre}`.")
                    if log_channel:
                        await log_channel.send(f"⚠️ **{member.name}** tenía clave válida, pero rol `{rol_nombre}` no encontrado.")
                return

        await member.send("❌ Clave incorrecta. Contacta con un admin si crees que es un error.")
        if log_channel:
            await log_channel.send(f"❌ **{member.name}** falló en la verificación con clave inválida.")

    except Exception as e:
        print(f"[ERROR] {e}")
        if log_channel:
            await log_channel.send(f"❗ Error verificando a **{member.name}**: `{e}`")
        try:
            await member.send("⚠️ Hubo un error al procesar tu verificación.")
        except:
            pass

@bot.command(name="testclave")
async def test_clave(ctx, clave: str = None):
    """Prueba una clave sin aplicar cambios (solo admin)"""
    
    # Verificamos si el usuario es administrador en algún servidor
    es_admin = False
    if isinstance(ctx.channel, discord.DMChannel):
        # En DM, verificamos si es admin en algún servidor compartido
        for guild in bot.guilds:
            member = guild.get_member(ctx.author.id)
            if member and member.guild_permissions.administrator:
                es_admin = True
                break
    else:
        # En canal de servidor, verificamos permisos normalmente
        es_admin = ctx.author.guild_permissions.administrator
    
    # Si no es administrador, denegamos el acceso
    if not es_admin:
        await ctx.send("❌ Necesitas permisos de Administrador para usar este comando.")
        return
    
    # Si no se proporciona la clave
    if clave is None:
        await ctx.send("❌ Uso: `!testclave [clave]`")
        return
    
    try:
        # Refrescamos la conexión a Google Sheets para evitar timeout
        # global client, sheet
        # if client.auth.expired:
        #     client.login()
        # sheet = client.open(GOOGLE_SHEET_NAME).worksheet(GOOGLE_SHEET_TAB)
        
        # Buscamos la clave en la hoja
        rows = sheet.get_all_records()
        encontrado = False
        
        for row in rows:
            if row["Clave"] == clave.strip():
                nombre = row["Nombre Discord"]
                rol_nombre = row["Rol Asignado"]
                
                # Verificamos si el rol existe (solo si estamos en un servidor)
                rol_status = "❓ No se puede verificar en DM"
                if not isinstance(ctx.channel, discord.DMChannel):
                    role = discord.utils.get(ctx.guild.roles, name=rol_nombre)
                    rol_status = "✅ Rol existe" if role else "⚠️ Rol no encontrado"
                else:
                    # En DM, intentamos verificar en todos los servidores compartidos
                    rol_encontrado = False
                    for guild in bot.guilds:
                        role = discord.utils.get(guild.roles, name=rol_nombre)
                        if role:
                            rol_status = f"✅ Rol existe en {guild.name}"
                            rol_encontrado = True
                            break
                    if not rol_encontrado:
                        rol_status = "⚠️ Rol no encontrado en ningún servidor"
                
                # Enviamos el resultado en un mensaje embebido para mejor formato
                embed = discord.Embed(
                    title="✅ Prueba de Clave",
                    description=f"Resultado para la clave: `{clave}`",
                    color=0x00ff00
                )
                embed.add_field(name="Nombre a asignar", value=nombre, inline=False)
                embed.add_field(name="Rol a asignar", value=rol_nombre, inline=True)
                embed.add_field(name="Estado del rol", value=rol_status, inline=True)
                embed.set_footer(text="Esta es solo una prueba, no se ha aplicado ningún cambio")
                
                await ctx.send(embed=embed)
                encontrado = True
                
                # Registramos en el canal de logs
                if log_channel:
                    where = "en DM" if isinstance(ctx.channel, discord.DMChannel) else f"en #{ctx.channel.name}"
                    await log_channel.send(f"🔍 **{ctx.author.name}** probó la clave `{clave}` {where} - Asignaría: `{nombre}` con rol `{rol_nombre}`")
                break
        
        if not encontrado:
            await ctx.send("❌ Clave no encontrada en la hoja de cálculo.")
            
            # Registramos en el canal de logs
            if log_channel:
                where = "en DM" if isinstance(ctx.channel, discord.DMChannel) else f"en #{ctx.channel.name}"
                await log_channel.send(f"🔍 **{ctx.author.name}** probó una clave inválida {where}: `{clave}`")
                
    except Exception as e:
        print(f"[ERROR] {e}")
        await ctx.send(f"❗ Error al probar la clave: `{e}`")
        
        # Registramos el error en el canal de logs
        if log_channel:
            await log_channel.send(f"❗ Error en comando testclave por **{ctx.author.name}**: `{e}`")


bot.run(DISCORD_TOKEN)
