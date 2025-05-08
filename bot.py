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
@has_permissions(administrator=True)  # Solo administradores pueden usar este comando
async def test_clave(ctx, clave: str = None):
    """Prueba una clave sin aplicar cambios (solo admin)"""
    
    # Si no se proporciona la clave
    if clave is None:
        await ctx.send("❌ Uso: `!testclave [clave]`")
        return
    
    try:
        # Verificamos que se ejecute en un canal y no en DM por seguridad
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("❌ Este comando solo se puede usar en canales del servidor, no en DM.")
            return
            
        # Refrescamos la conexión a Google Sheets para evitar timeout
        global client, sheet
        if client.auth.expired:
            client.login()
        sheet = client.open(GOOGLE_SHEET_NAME).worksheet(GOOGLE_SHEET_TAB)
        
        # Buscamos la clave en la hoja
        rows = sheet.get_all_records()
        encontrado = False
        
        for row in rows:
            if row["Clave"] == clave.strip():
                nombre = row["Nombre Discord"]
                rol_nombre = row["Rol Asignado"]
                
                # Verificamos si el rol existe
                role = discord.utils.get(ctx.guild.roles, name=rol_nombre)
                rol_status = "✅ Rol existe" if role else "⚠️ Rol no encontrado"
                
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
                    await log_channel.send(f"🔍 **{ctx.author.name}** probó la clave `{clave}` - Asignaría: `{nombre}` con rol `{rol_nombre}`")
                break
        
        if not encontrado:
            await ctx.send("❌ Clave no encontrada en la hoja de cálculo.")
            
            # Registramos en el canal de logs
            if log_channel:
                await log_channel.send(f"🔍 **{ctx.author.name}** probó una clave inválida: `{clave}`")
                
    except Exception as e:
        print(f"[ERROR] {e}")
        await ctx.send(f"❗ Error al probar la clave: `{e}`")
        
        # Registramos el error en el canal de logs
        if log_channel:
            await log_channel.send(f"❗ Error en comando testclave por **{ctx.author.name}**: `{e}`")

bot.run(DISCORD_TOKEN)
