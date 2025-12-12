import os
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from supabase import create_client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------------------
# BOT TOKEN
# ---------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN not found in secrets")

# ---------------------------
# SUPABASE CLIENT
# ---------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase URL or Key not found in secrets")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------
# IN-MEMORY CACHE
# ---------------------------
# Structure: {user_id: {"tokens": int, "last_update": datetime}}
user_cache = defaultdict(lambda: {"tokens": 0, "last_update": datetime.now()})

# ---------------------------
# CACHE FLUSH TO SUPABASE
# ---------------------------
async def flush_cache():
    while True:
        now = datetime.now()
        for user_id, data in list(user_cache.items()):
            # Only flush if updated more than 10 seconds ago
            if now - data["last_update"] >= timedelta(seconds=10):
                # Upsert into Supabase
                supabase.table("users").upsert({
                    "user_id": user_id,
                    "tokens": data["tokens"]
                }, on_conflict="user_id").execute()

                # Reset in-memory cache for this user
                user_cache[user_id]["tokens"] = 0
                user_cache[user_id]["last_update"] = datetime.now()
        await asyncio.sleep(5)  # check every 5 seconds

# ---------------------------
# TELEGRAM BOT HANDLERS
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Tap Egg 🥚", callback_data="tap_egg")]]
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome! Tap the egg to get tokens.", reply_markup=markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Increment in-memory token count
    user_cache[user_id]["tokens"] += 1
    user_cache[user_id]["last_update"] = datetime.now()

    # Optionally, show current token count in message
    await query.edit_message_text(
        text=f"You tapped the egg! Tokens: {user_cache[user_id]['tokens']}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Tap Egg 🥚", callback_data="tap_egg")]])
    )

# ---------------------------
# MAIN BOT RUN
# ---------------------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    # Start background cache flush
    asyncio.create_task(flush_cache())

    print("Bot is running...")
    app.run_polling()
