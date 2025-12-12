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

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------
# IN-MEMORY CACHE
# ---------------------------
user_cache = defaultdict(lambda: {"tokens": 0, "last_update": datetime.now()})

# ---------------------------
# FLUSH CACHE TO SUPABASE
# ---------------------------
async def flush_cache():
    while True:
        now = datetime.now()
        for user_id, data in list(user_cache.items()):
            if now - data["last_update"] >= timedelta(seconds=10):
                # Upsert using Supabase REST client
                supabase.table("users").upsert({
                    "user_id": user_id,
                    "tokens": data["tokens"]
                }, on_conflict="user_id").execute()

                # Reset cache
                user_cache[user_id]["tokens"] = 0
                user_cache[user_id]["last_update"] = datetime.now()
        await asyncio.sleep(5)

# ---------------------------
# TELEGRAM BOT HANDLERS
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Tap Egg 🥚", callback_data="tap_egg")]]
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome! Tap the egg to get tokens.", reply_markup=markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Update in-memory cache
    user_cache[user_id]["tokens"] += 1
    user_cache[user_id]["last_update"] = datetime.now()

# ---------------------------
# RUN BOT
# ---------------------------
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    # Start cache flush
    asyncio.create_task(flush_cache())

    print("Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
