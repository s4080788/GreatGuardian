import discord
import asyncio
import json
import requests
from discord.ext import commands
from discord.utils import utcnow
from datetime import datetime, timedelta
import os
from flask import Flask
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "I'm awake!"

def run_server():
    app.run(host="0.0.0.0", port=8080)

# Запускаем сервер в отдельном потоке
server_thread = threading.Thread(target=run_server)
server_thread.start()

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

discord_token = os.getenv("DISCORD_TOKEN")
cloudflare_api_key = os.getenv("CLOUDFLARE_API_KEY")
cloudflare_ai_url = os.getenv("CLOUDFLARE_AI_URL")



# Роли, которые используются для пинга администраторов
ADMIN_ROLE = "Администратор"  # Роль админа для пинга

# Загрузка репутации
try:
    with open("reputation.json", "r") as f:
        reputation = json.load(f)
except FileNotFoundError:
    reputation = {}

def save_reputation():
    with open("reputation.json", "w") as f:
        json.dump(reputation, f)

# Запуск бота
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def analyze_with_cloudflare(text):
    headers = {
        "Authorization": f"Bearer {cloudflare_api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "messages": [
            {"role": "system", "content": "You are a moderator. You must check that the message does not contain direct insults or provocations. Be fair, if you doubt a violation, then there is no violation, also there is may be joke. Answer only 'there is a violation' or 'there is no violation'."},
            {"role": "user", "content": text}
        ]
    }
    response = requests.post(cloudflare_ai_url, json=data, headers=headers)
    if response.status_code == 200:
        # Извлекаем результат из ответа
        analysis = response.json().get("result", {}).get("response", "")
        # Если это строка, проверяем на наличие агрессии или провокации
        return "there is a violation" in analysis.lower()
    return False

@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен!')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Анализируем сообщение через Cloudflare 
    is_toxic = analyze_with_cloudflare(message.content)

    if is_toxic:
        user_id = str(message.author.id)
        reputation[user_id] = min(reputation.get(user_id, 0) + 1, 3)
        save_reputation()

        if reputation[user_id] >= 3:  # При 3 и более нарушениях мут
            if message.author.guild_permissions.administrator:
                await message.channel.send(f"{message.author.mention}, вы администратор и я не могу выдать вам мут. Пожалуйста, следите за своим поведением.")
            else:
                # Временно блокируем пользователя от отправки сообщений
                await message.author.timeout(utcnow() + timedelta(seconds=60))  # 60 секунд
                await message.channel.send(f'🚨 {message.author.mention} выдан мут за агрессию на 60 секунд!')
            # Пинг администраторов с ролью "Администратор"
            admin_role = discord.utils.get(message.guild.roles, name=ADMIN_ROLE)
            if admin_role:
                await message.channel.send(f'{admin_role.mention}, конфликт требует внимания!')
        else:
            await message.channel.send(f'⚠️ {message.author.mention}, пожалуйста, избегайте провокаций и агрессии в общении.')
    else:
        user_id = str(message.author.id)
        if reputation[user_id] >= 0:
            reputation[user_id] = reputation.get(user_id, 0) - 1
            save_reputation()
            
    await bot.process_commands(message)

@bot.command(name="rep")
async def reputation_command(ctx, member: discord.Member = None):
    # Если пользователь не указан, проверяем репутацию отправителя
    if member is None:
        member = ctx.author

    user_id = str(member.id)
    user_reputation = reputation.get(user_id, 0)

    await ctx.send(f"Репутация пользователя {member.mention}: {user_reputation}")
    
bot.run(discord_token)
