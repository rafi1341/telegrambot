import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------------------
# DATABASE CONNECTION (Railway Postgres)
# ---------------------------
conn = psycopg2.connect(
    host="postgres.railway.internal",
    user="postgres",
    password="qAOgzdpdyOBCVjGrDQzAuIEgjiUXHGqi",
    database="railway"
)
cursor = conn.cursor()

# Make sure the table exists
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
# Structure: {user_id: {"tokens": int, "last_update": datetime}}
user_cache = defaultdict(lambda: {"tokens": 0, "last_update": datetime.now()})

# ---------------------------
# CACHE FLUSH FUNCTION
# ---------------------------
def flush_cache():
    while True:
        now = datetime.now()
        for user_id, data in list(user_cache.items()):
            # Only flush users updated >10 seconds ago
            if now - data["last_update"] >= timedelta(seconds=10):
                cursor.execute(
                    """
                    INSERT INTO users (user_id, tokens)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET tokens = users.tokens + EXCLUDED.tokens
                    """,
                    (user_id, data["tokens"])
                )
                conn.commit()
                user_cache[user_id]["tokens"] = 0  # reset cache
        time.sleep(5)  # check every 5 seconds

# Start the flush thread
threading.Thread(target=flush_cache, daemon=True).start()

# ---------------------------
# BOT LOGIC
# ---------------------------
BOT_TOKEN = "8210266665:AAFArla_n3LA7VqG34h6vxiRK0tFkEdqu-4"

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [[InlineKeyboardButton("Tap Egg 🥚", callback_data="tap_egg")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome! Tap the egg to get tokens.", reply_markup=reply_markup)

# Handle button taps
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Add tokens to cache
    user_cache[user_id]["tokens"] += 1
    user_cache[user_id]["last_update"] = datetime.now()

    # Optionally, show current balance (cached + DB)
    cursor.execute("SELECT tokens FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    db_tokens = row[0] if row else 0
    cached_tokens = user_cache[user_id]["tokens"]
    total_tokens = db_tokens + cached_tokens

    await query.edit_message_text(f"You tapped the egg! 🥚\nTokens: {total_tokens}")

# /balance command to check tokens
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT tokens FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    db_tokens = row[0] if row else 0
    cached_tokens = user_cache[user_id]["tokens"]
    total_tokens = db_tokens + cached_tokens
    await update.message.reply_text(f"Your total tokens: {total_tokens}")

# ---------------------------
# BOT INITIALIZATION
# ---------------------------
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("balance", balance))
app.add_handler(CallbackQueryHandler(button))

# Run bot
app.run_polling()
