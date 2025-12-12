from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask, request, jsonify
import threading
import os
import psycopg2
import json
import time

# -----------------------------
# Environment variables
# -----------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = os.environ.get("WEB_APP_URL")
PG_HOST = os.environ.get("PG_HOST")
PG_PORT = os.environ.get("PG_PORT")
PG_USER = os.environ.get("PG_USER")
PG_PASSWORD = os.environ.get("PG_PASSWORD")
PG_DATABASE = os.environ.get("PG_DATABASE")
PG_SSLMODE = os.environ.get("PG_SSLMODE", "require")
API_SECRET = os.environ.get("API_SECRET")  # For mini app authentication

if not all([BOT_TOKEN, WEB_APP_URL, PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE, API_SECRET]):
    raise Exception("One or more environment variables are missing!")

# -----------------------------
# Database connection
# -----------------------------
def get_db():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DATABASE,
        sslmode=PG_SSLMODE
    )

# -----------------------------
# JSON backup
# -----------------------------
CACHE_FILE = "cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(user_cache, f)

user_cache = load_cache()  # {user_id: {"balance": int}}

# -----------------------------
# Flush cache to DB + JSON
# -----------------------------
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
            print("Flushed cache to DB + JSON backup. Current cache:", user_cache)
        except Exception as e:
            print("Flush error:", e)
        time.sleep(30)  # flush interval

threading.Thread(target=flush_worker, daemon=True).start()

# -----------------------------
# Telegram Bot Handlers
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    keyboard = [[InlineKeyboardButton("Launch App", web_app=WebAppInfo(url=WEB_APP_URL))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_photo(
        chat_id=chat_id,
        photo=open("banner.png", "rb"),
        caption="Welcome to TokenHatch! 🥚\nHatch creatures, get $EGG crypto points, and earn airdrops!",
        reply_markup=reply_markup
    )

    uid = str(chat_id)
    if uid not in user_cache:
        user_cache[uid] = {"balance": 0}
        save_cache()

# -----------------------------
# Function to update tokens
# -----------------------------
def add_tokens(user_id, tokens):
    uid = str(user_id)
    if uid not in user_cache:
        user_cache[uid] = {"balance": 0}
    user_cache[uid]["balance"] += tokens
    print(f"Added {tokens} tokens to user {uid}. New balance: {user_cache[uid]['balance']}")
    save_cache()

# -----------------------------
# Flask app to receive updates from mini app
# -----------------------------
flask_app = Flask(__name__)

@flask_app.route("/update_tokens", methods=["POST"])
def update_tokens():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    user_id = data.get("user_id")
    tokens = data.get("tokens")
    api_secret = data.get("api_secret")

    if api_secret != API_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    if not user_id or not isinstance(tokens, int):
        return jsonify({"error": "Invalid user_id or tokens"}), 400

    add_tokens(user_id, tokens)
    return jsonify({"status": "success", "user_id": user_id, "tokens": tokens})

def run_flask():
    flask_app.run(host="0.0.0.0", port=5000)

threading.Thread(target=run_flask, daemon=True).start()

# -----------------------------
# Start Telegram Bot
# -----------------------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("Bot started...")
    app.run_polling()
