import os
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
import urllib.parse as urlparse
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------------------
# TELEGRAM BOT TOKEN
# ---------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_TOKEN = "8210266665:AAFArla_n3LA7VqG34h6vxiRK0tFkEdqu-4" 
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN environment variable not found!")

# ---------------------------
# DATABASE CONNECTION
# ---------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL environment variable not found!")

url = urlparse.urlparse(DATABASE_URL)
conn = psycopg2.connect(
    dbname=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    tokens INT DEFAULT 0
)
""")
conn.commit()

# ---------------------------
# IN-MEMORY CACHE
# ---------------------------
user_cache = defaultdict(lambda: {"tokens": 0, "last_update": datetime.now()})

# ---------------------------
# ASYNC CACHE FLUSH
# ---------------------------
async def flush_cache():
    while True:
        now = datetime.now()
        for user_id, data in list(user_cache.items()):
            if now - data["last_update"] >= timedelta(seconds=10):
                cursor.execute("""
                    INSERT INTO users (user_id, tokens)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET tokens = users.tokens + EXCLUDED.tokens
                """, (user_id, data["tokens"]))
                conn.commit()
                user_cache[user_id]["tokens"] = 0
                user_cache[user_id]["last_update"] = datetime.now()
        await asyncio.sleep(5)

# ---------------------------
# TELEGRAM BOT HANDLERS
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Tap Egg 🥚", callback_data="tap_egg")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome! Tap the egg to get tokens.", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_cache[user_id]["tokens"] += 1
    user_cache[user_id]["last_update"] = datetime.now()

# ---------------------------
# MAIN
# ---------------------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    # Run flush cache in background
    asyncio.create_task(flush_cache())

    # Start bot
    asyncio.run(app.run_polling())
