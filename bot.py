import os
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from supabase import create_client, Client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------------------
# SUPABASE CONNECTION
# ---------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("SUPABASE_URL or SUPABASE_KEY not found in environment variables!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Ensure 'users' table exists with columns: user_id (BIGINT), tokens (INT)
# You can create it manually in Supabase GUI or via SQL
# Example SQL:
# CREATE TABLE IF NOT EXISTS users (
#   user_id BIGINT PRIMARY KEY,
#   tokens INT DEFAULT 0
# );

# ---------------------------
# IN-MEMORY CACHE
# ---------------------------
# Structure: {user_id: {"tokens": int, "last_update": datetime}}
user_cache = defaultdict(lambda: {"tokens": 0, "last_update": datetime.now()})

# ---------------------------
# CACHE FLUSH FUNCTION
# ---------------------------
async def flush_cache():
    now = datetime.now()
    for user_id, data in list(user_cache.items()):
        if now - data["last_update"] >= timedelta(seconds=10):
            # Update Supabase
            try:
                # Upsert the user tokens
                supabase.table("users").upsert({
                    "user_id": user_id,
                    "tokens": data["tokens"]
                }, on_conflict="user_id").execute()
            except Exception as e:
                print(f"Error updating Supabase: {e}")

            # Reset cache
            user_cache[user_id]["tokens"] = 0
            user_cache[user_id]["last_update"] = datetime.now()

# ---------------------------
# TELEGRAM BOT LOGIC
# ---------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN environment variable not found!")

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

    # Increment token in cache
    user_cache[user_id]["tokens"] += 1
    user_cache[user_id]["last_update"] = datetime.now()

    # Optional: show current tokens in cache
    await query.edit_message_text(
        text=f"You tapped the egg! Tokens in cache: {user_cache[user_id]['tokens']}",
        reply_markup=query.message.reply_markup
    )

# ---------------------------
# MAIN
# ---------------------------
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    # Schedule flush_cache every 5 seconds
    app.job_queue.run_repeating(lambda ctx: asyncio.create_task(flush_cache()), interval=5)

    print("Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
