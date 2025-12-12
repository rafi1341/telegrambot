from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import os
import psycopg2
import json
import time
import threading

# -------------------------------------------------------------
#  Load environment variables
# -------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN environment variable not found!")

WEB_APP_URL = os.environ.get("WEB_APP_URL")
if not WEB_APP_URL:
    raise Exception("WEB_APP_URL environment variable not found!")

PG_HOST = os.getenv("PG_HOST")
PG_PORT = os.getenv("PG_PORT")
PG_USER = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")
PG_DATABASE = os.getenv("PG_DATABASE")
PG_SSLMODE = os.getenv("PG_SSLMODE", "require")

# -------------------------------------------------------------
#  Database connection
# -------------------------------------------------------------

def get_db():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DATABASE,
        sslmode=PG_SSLMODE
    )

# -------------------------------------------------------------
#  JSON backup system
# -------------------------------------------------------------

CACHE_FILE = "cache.json"

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(user_cache, f)

# In-memory user cache {user_id: {"balance": int}}
user_cache = load_cache()

# -------------------------------------------------------------
#  Automatic flusher (every 30 sec)
# -------------------------------------------------------------

def flush_worker():
    while True:
        try:
            if not user_cache:
                time.sleep(30)
                continue

            conn = get_db()
            cur = conn.cursor()

            for uid, data in user_cache.items():
                cur.execute("""
                    INSERT INTO users (user_id, balance)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id)
                    DO UPDATE SET balance = EXCLUDED.balance;
                """, (uid, data.get("balance", 0)))

            conn.commit()
            cur.close()
            conn.close()

            save_cache()

            print("Flushed to DB + JSON backup.")

        except Exception as e:
            print("Flush error:", e)

        time.sleep(30)

# Start the background thread
threading.Thread(target=flush_worker, daemon=True).start()

# -------------------------------------------------------------
#  Telegram bot handler
# -------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    keyboard = [
        [InlineKeyboardButton("Launch App", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_photo(
        chat_id=chat_id,
        photo=open("banner.png", "rb"),
        caption="Welcome to TokenHatch! 🥚\nHatch creatures, get $EGG crypto points, and earn airdrops!",
        reply_markup=reply_markup
    )

    # Initialize user balance in cache if not exist
    if str(chat_id) not in user_cache:
        user_cache[str(chat_id)] = {"balance": 0}
        save_cache()

# -------------------------------------------------------------
#  Start bot
# -------------------------------------------------------------

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    print("Bot started...")
    app.run_polling()
