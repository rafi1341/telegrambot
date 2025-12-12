import os
import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict
import urllib.parse as urlparse
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ---------------------------------------
# BOT TOKEN (for testing you can hardcode)
# ---------------------------------------
# BOT_TOKEN = "YOUR_REAL_TOKEN_HERE"
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN missing!")

# ---------------------------------------
# DATABASE CONNECTION
# ---------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL missing!")

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

# ---------------------------------------
# IN-MEMORY CACHE
# ---------------------------------------
user_cache = defaultdict(lambda: {"tokens": 0, "last_update": datetime.now()})

# ---------------------------------------
# CACHE FLUSHER (thread)
# ---------------------------------------
def flush_cache():
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

                # reset cache
                user_cache[user_id]["tokens"] = 0
                user_cache[user_id]["last_update"] = datetime.now()

        time.sleep(5)

# Start the flush thread
threading.Thread(target=flush_cache, daemon=True).start()

# ---------------------------------------
# TELEGRAM HANDLERS
# ---------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Tap Egg 🥚", callback_data="tap_egg")]]
    await update.message.reply_text("Welcome! Tap the egg to earn tokens.", 
                                    reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_cache[user_id]["tokens"] += 1
    user_cache[user_id]["last_update"] = datetime.now()

# ---------------------------------------
# START BOT
# ---------------------------------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    print("Bot is running...")
    app.run_polling()
