# bot.py
from flask import Flask, request, jsonify, send_from_directory
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import sqlite3
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = "https://your-render-url.onrender.com"

# ----------------------------
# SQLite database setup
# ----------------------------
DB_FILE = "tokens.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users_tokens (
            user_id TEXT PRIMARY KEY,
            tokens INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_tokens(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT tokens FROM users_tokens WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_tokens(user_id, new_tokens):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO users_tokens(user_id, tokens)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET tokens=excluded.tokens
    """, (user_id, new_tokens))
    conn.commit()
    conn.close()

# ----------------------------
# Flask app for mini app API
# ----------------------------
app = Flask(__name__, static_folder='static')

@app.route("/")
def index():
    return send_from_directory('static', 'index.html')

@app.route("/get_tokens/<user_id>")
def api_get_tokens(user_id):
    return jsonify({"tokens": get_tokens(user_id)})

@app.route("/add_token/<user_id>", methods=["POST"])
def api_add_token(user_id):
    data = request.json
    amount = data.get("amount", 1)
    current = get_tokens(user_id)
    new_total = current + amount
    update_tokens(user_id, new_total)
    return jsonify({"tokens": new_total})

# ----------------------------
# Telegram bot
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("Launch App💵", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=open("static/banner.png", "rb"),
        caption="Welcome to TokenHatch! 🥚 Collect eggs and earn $EGG tokens!",
        reply_markup=reply_markup
    )

def run_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.run_polling()

# ----------------------------
# Main entry
# ----------------------------
if __name__ == "__main__":
    init_db()
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
