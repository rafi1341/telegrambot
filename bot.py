from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import os
import psycopg2
import time
import requests
import json

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = os.environ.get("WEB_APP_URL")
PG_HOST = os.environ.get("PG_HOST")
PG_PORT = os.environ.get("PG_PORT")
PG_USER = os.environ.get("PG_USER")
PG_PASSWORD = os.environ.get("PG_PASSWORD")
PG_DATABASE = os.environ.get("PG_DATABASE")
PG_SSLMODE = os.environ.get("PG_SSLMODE", "require")
API_SECRET = os.environ.get("API_SECRET")
RENDER_URL = os.environ.get("RENDER_URL")

if not all([BOT_TOKEN, WEB_APP_URL, PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE, API_SECRET]):
    raise Exception("One or more environment variables are missing!")

# --- DATABASE CONNECTION ---
def get_db():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DATABASE,
        sslmode=PG_SSLMODE
    )

# --- INIT DATABASE (UPDATED) ---
def init_db():
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # 1. Create Table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                current_egg_index INTEGER DEFAULT 0,
                current_egg_hp BIGINT DEFAULT 0,
                creatures_data JSONB DEFAULT '{}',
                referred_by BIGINT,
                referral_claimed BOOLEAN DEFAULT FALSE,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 2. Alter Table to add new columns (Safe to run even if columns exist)
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS current_egg_index INTEGER DEFAULT 0;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS current_egg_hp BIGINT DEFAULT 0;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS creatures_data JSONB DEFAULT '{}';")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by BIGINT;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_claimed BOOLEAN DEFAULT FALSE;")
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database initialized/updated successfully!")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")

# --- CACHE ---
# Updated cache to hold full game data
user_cache = {}  

def load_cache_from_db():
    try:
        conn = get_db()
        cur = conn.cursor()
        # Select ALL game columns
        cur.execute("""
            SELECT user_id, balance, current_egg_index, current_egg_hp, creatures_data 
            FROM users
        """)
        rows = cur.fetchall()
        for row in rows:
            user_cache[row[0]] = {
                "balance": row[1],
                "current_egg_index": row[2],
                "current_egg_hp": row[3],
                "creatures": row[4] if isinstance(row[4], dict) else {}
            }
        cur.close()
        conn.close()
        print(f"✅ Loaded {len(user_cache)} users from database.")
    except Exception as e:
        print(f"❌ Error loading cache: {e}")

# --- BACKGROUND WORKERS ---

def flush_worker():
    while True:
        try:
            time.sleep(10)  # Flush every 10 seconds
            if not user_cache:
                continue

            conn = get_db()
            cur = conn.cursor()
            
            for uid, data in user_cache.items():
                # Serialize creatures dict to JSON string for Postgres
                creatures_json = json.dumps(data.get("creures", {}))
                
                cur.execute("""
                    INSERT INTO users (user_id, balance, current_egg_index, current_egg_hp, creatures_data, last_updated)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                        balance = EXCLUDED.balance,
                        current_egg_index = EXCLUDED.current_egg_index,
                        current_egg_hp = EXCLUDED.current_egg_hp,
                        creatures_data = EXCLUDED.creatures_data,
                        last_updated = CURRENT_TIMESTAMP;
                """, (
                    uid, 
                    data.get("balance", 0), 
                    data.get("current_egg_index", 0),
                    data.get("current_egg_hp", 0),
                    creatures_json
                ))
            
            conn.commit()
            cur.close()
            conn.close()
            print(f"🔄 Synced {len(user_cache)} users to database.")
            
        except Exception as e:
            print(f"❌ Flush error: {e}")

def keep_alive_worker():
    if not RENDER_URL:
        return
    while True:
        try:
            time.sleep(600)
            requests.get(RENDER_URL, timeout=5)
            print(f"💓 Keep-alive ping sent.")
        except Exception as e:
            print(f"⚠️ Keep-alive ping failed: {e}")

# --- TELEGRAM HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    uid = str(chat_id)
    
    # 1. CAPTURE REFERRAL ID
    # If user clicked a link like t.me/bot?start=123, context.args will be ['123']
    referrer_id = None
    if context.args:
        referrer_id = context.args[0]
        print(f"📢 Referral detected from {referrer_id}")

    # 2. KEYBOARD SETUP
    keyboard = [[InlineKeyboardButton("🥚 Launch App", web_app=WebAppInfo(url=WEB_APP_URL))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # 3. SEND MESSAGE
    try:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=open("banner.png", "rb"),
            caption="HatchToken lets you earn real money💲 from tasks today, while unused rewards hatch🥚 into $HATCH tokens later.",
            reply_markup=reply_markup
        )
    except FileNotFoundError:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Welcome to TokenHatch! 🥚\nHatch creatures, get $EGG crypto points, and earn airdrops!",
            reply_markup=reply_markup
        )

    # 4. HANDLE REFERRAL LOGIC
    if uid in user_cache:
        print(f"ℹ️ Existing user {uid} loaded from cache.")
    else:
        print(f"🆕 New user {uid}. Checking referral...")
        
        # Bonus Amounts
        REFERRER_BONUS = 1000
        REFEREE_BONUS = 500
        
        try:
            conn = get_db()
            cur = conn.cursor()
            
            # Check if referrer exists
            referrer_valid = False
            if referrer_id:
                cur.execute("SELECT user_id FROM users WHERE user_id = %s", (referrer_id,))
                if cur.fetchone():
                    referrer_valid = True
            
            # Insert New User
            cur.execute("""
                INSERT INTO users (user_id, balance, current_egg_index, current_egg_hp, creatures_data, referred_by, referral_claimed)
                VALUES (%s, %s, 0, 0, '{}', %s, %s)
            """, (uid, REFEREE_BONUS, referrer_id, referrer_valid))
            
            # Give Referrer Bonus
            if referrer_valid:
                cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (REFERRER_BONUS, referrer_id))
            
            conn.commit()
            cur.close()
            conn.close()
            
            # Update Cache immediately
            user_cache[uid] = {
                "balance": REFEREE_BONUS,
                "current_egg_index": 0,
                "current_egg_hp": 0,
                "creatures": {}
            }
            
            print(f"✅ User created. Referral: {referrer_valid}")
            
        except Exception as e:
            print(f"❌ DB Error during start: {e}")

# --- FLASK APP (API) ---
flask_app = Flask(__name__)
CORS(flask_app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type"]}})

@flask_app.route("/update_tokens", methods=["POST"])
def update_tokens():
    data = request.json
    if not data: return jsonify({"error": "No data"}), 400

    user_id = str(data.get("user_id"))
    tokens = int(data.get("tokens", 0))
    api_secret = data.get("api_secret")

    if api_secret != API_SECRET: return jsonify({"error": "Unauthorized"}), 401

    if user_id not in user_cache: 
        user_cache[user_id] = {"balance": 0, "current_egg_index": 0, "current_egg_hp": 0, "creatures": {}}
    
    # Update Balance
    user_cache[user_id]["balance"] += tokens
    
    return jsonify({"status": "success", "new_balance": user_cache[user_id]["balance"]})

@flask_app.route("/save_game_state", methods=["POST"]) # NEW ENDPOINT
def save_game_state():
    data = request.json
    if not data: return jsonify({"error": "No data"}), 400

    user_id = str(data.get("user_id"))
    api_secret = data.get("api_secret")

    if api_secret != API_SECRET: return jsonify({"error": "Unauthorized"}), 401

    if user_id not in user_cache:
        user_cache[user_id] = {"balance": 0, "current_egg_index": 0, "current_egg_hp": 0, "creatures": {}}

    # Update Full Game State
    user_cache[user_id]["balance"] = data.get("balance", 0)
    user_cache[user_id]["current_egg_index"] = data.get("current_egg_index", 0)
    user_cache[user_id]["current_egg_hp"] = data.get("current_egg_hp", 0)
    
    # Handle Creatures JSON
    creatures_data = data.get("creures", {})
    user_cache[user_id]["creatures"] = creatures_data

    return jsonify({"status": "saved"})

@flask_app.route("/load_game_state", methods=["POST"]) # NEW ENDPOINT
def load_game_state():
    data = request.json
    if not data: return jsonify({"error": "No data"}), 400

    user_id = str(data.get("user_id"))
    api_secret = data.get("api_secret")

    if api_secret != API_SECRET: return jsonify({"error": "Unauthorized"}), 401

    # Return from Cache
    if user_id in user_cache:
        return jsonify({"status": "success", "data": user_cache[user_id]})
    else:
        return jsonify({"status": "new_user", "data": {}})

@flask_app.route("/get_balance", methods=["POST"])
def get_balance():
    data = request.json
    if not data: return jsonify({"error": "No data"}), 400

    user_id = str(data.get("user_id"))
    api_secret = data.get("api_secret")

    if api_secret != API_SECRET: return jsonify({"error": "Unauthorized"}), 401

    if user_id in user_cache:
        return jsonify({"balance": user_cache[user_id]["balance"]})
    return jsonify({"balance": 0})

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("🚀 Starting TokenHatch Bot & API Server...")
    
    init_db()         # Setup DB Tables
    load_cache_from_db() # Load existing users into RAM
    
    threading.Thread(target=flush_worker, daemon=True).start()
    threading.Thread(target=keep_alive_worker, daemon=True).start()
    threading.Thread(target=run_flask, daemon=True).start()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    print("✅ Bot polling started...")
    app.run_polling()
