from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask, request, jsonify
import threading
import os
import psycopg2
import time
import requests

# Environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = os.environ.get("WEB_APP_URL")
PG_HOST = os.environ.get("PG_HOST")
PG_PORT = os.environ.get("PG_PORT")
PG_USER = os.environ.get("PG_USER")
PG_PASSWORD = os.environ.get("PG_PASSWORD")
PG_DATABASE = os.environ.get("PG_DATABASE")
PG_SSLMODE = os.environ.get("PG_SSLMODE", "require")
API_SECRET = os.environ.get("API_SECRET")
RENDER_URL = os.environ.get("RENDER_URL")  # Add your Render service URL here

if not all([BOT_TOKEN, WEB_APP_URL, PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE, API_SECRET]):
    raise Exception("One or more environment variables are missing!")

# Database connection
def get_db():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DATABASE,
        sslmode=PG_SSLMODE
    )

# Initialize database table
def init_db():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Database initialization error: {e}")

# In-memory cache
user_cache = {}  # {user_id: {"balance": int}}

# Load existing users from DB into cache on startup
def load_cache_from_db():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT user_id, balance FROM users")
        rows = cur.fetchall()
        for row in rows:
            user_cache[row[0]] = {"balance": row[1]}
        cur.close()
        conn.close()
        print(f"Loaded {len(user_cache)} users from database into cache")
    except Exception as e:
        print(f"Error loading cache from DB: {e}")

# Flush cache to DB every 30 seconds
def flush_worker():
    while True:
        try:
            time.sleep(10)
            
            if not user_cache:
                print("Cache empty, skipping flush")
                continue

            conn = get_db()
            cur = conn.cursor()
            
            for uid, data in user_cache.items():
                cur.execute("""
                    INSERT INTO users (user_id, balance, last_updated)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id)
                    DO UPDATE SET 
                        balance = EXCLUDED.balance,
                        last_updated = CURRENT_TIMESTAMP;
                """, (uid, data.get("balance", 0)))
            
            conn.commit()
            cur.close()
            conn.close()
            print(f"✅ Flushed {len(user_cache)} users to database. Cache: {user_cache}")
            
        except Exception as e:
            print(f"❌ Flush error: {e}")

# Keep-alive ping to prevent Render spin-down
def keep_alive_worker():
    if not RENDER_URL:
        print("⚠️  RENDER_URL not set, skipping keep-alive pings")
        return
    
    while True:
        try:
            time.sleep(600)  # Ping every 10 minutes
            response = requests.get(RENDER_URL, timeout=5)
            print(f"💚 Keep-alive ping sent: {response.status_code}")
        except Exception as e:
            print(f"⚠️  Keep-alive ping failed: {e}")

# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    keyboard = [[InlineKeyboardButton("Launch App", web_app=WebAppInfo(url=WEB_APP_URL))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Check if banner.png exists, if not send text only
    try:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=open("banner.png", "rb"),
            caption="Welcome to TokenHatch! 🥚\nHatch creatures, get $EGG crypto points, and earn airdrops!",
            reply_markup=reply_markup
        )
    except FileNotFoundError:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Welcome to TokenHatch! 🥚\nHatch creatures, get $EGG crypto points, and earn airdrops!",
            reply_markup=reply_markup
        )

    # Initialize user in cache if not exists
    uid = str(chat_id)
    if uid not in user_cache:
        user_cache[uid] = {"balance": 0}
        print(f"New user {uid} added to cache")

# Function to update tokens
def add_tokens(user_id, tokens):
    uid = str(user_id)
    if uid not in user_cache:
        user_cache[uid] = {"balance": 0}
    user_cache[uid]["balance"] += tokens
    print(f"💰 Added {tokens} tokens to user {uid}. New balance: {user_cache[uid]['balance']}")

# Flask app to receive updates from mini app
flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Bot is running", "cached_users": len(user_cache)})

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
    return jsonify({
        "status": "success", 
        "user_id": user_id, 
        "tokens_added": tokens,
        "new_balance": user_cache[str(user_id)]["balance"]
    })

@flask_app.route("/get_balance", methods=["POST"])
def get_balance():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    user_id = str(data.get("user_id"))
    api_secret = data.get("api_secret")

    if api_secret != API_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    # Try cache first, then database
    if user_id in user_cache:
        balance = user_cache[user_id]["balance"]
    else:
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            if row:
                balance = row[0]
                user_cache[user_id] = {"balance": balance}
            else:
                balance = 0
                user_cache[user_id] = {"balance": 0}
        except Exception as e:
            print(f"Database error: {e}")
            return jsonify({"error": "Database error"}), 500

    return jsonify({"user_id": user_id, "balance": balance})

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

# Start everything
if __name__ == "__main__":
    print("🚀 Starting TokenHatch Bot...")
    
    # Initialize database
    init_db()
    
    # Load cache from database
    load_cache_from_db()
    
    # Start flush worker thread
    threading.Thread(target=flush_worker, daemon=True).start()
    
    # Start keep-alive worker thread
    threading.Thread(target=keep_alive_worker, daemon=True).start()
    
    # Start Flask in a separate thread
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Start Telegram Bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    print("✅ Bot started and polling...")
    app.run_polling()

