import discord
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
GOOGLE_SHEET_TAB = os.getenv("GOOGLE_SHEET_TAB")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_PATH, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).worksheet(GOOGLE_SHEET_TAB)

@bot.event
async def on_ready():
    print(f"✅ Bot listo como: {bot.user.name}")

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
                else:
                    await member.send(f"⚠️ Clave correcta, pero no se encontró el rol `{rol_nombre}` en el servidor.")
                return

        await member.send("❌ Clave incorrecta. Contacta con un admin si crees que es un error.")

    except Exception as e:
        print(f"[ERROR] {e}")
        try:
            await member.send("⚠️ Hubo un error al procesar tu verificación.")
        except:
            pass

bot.run(DISCORD_TOKEN)
