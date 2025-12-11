# bot.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import os
import json

# ----------------------------
# Configuration
# ----------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = "https://tokenhatch.onrender.com/?v=2"

# ----------------------------
# In-memory user scores
# ----------------------------
# Key: Telegram user ID, Value: token count
user_scores = {}

# ----------------------------
# /start command
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    score = user_scores.get(chat_id, 0)

    keyboard = [
        [InlineKeyboardButton("Launch App💵", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_photo(
        chat_id=chat_id,
        photo=open("banner.png", "rb"),
        caption=f"Welcome to TokenHatch! 🥚 Hatch creatures, get $EGG points!\nYour current score: {score}",
        reply_markup=reply_markup
    )

# ----------------------------
# Handle WebApp data
# ----------------------------
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ignore if no WebApp data
    if not update.web_app_data:
        return

    try:
        data = update.web_app_data.data
        payload = json.loads(data)
        user_id = update.effective_user.id
        new_score = payload.get("score", 0)

        # Update user score
        user_scores[user_id] = new_score

        # Acknowledge back
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Your new $EGG score is {new_score}!"
        )

    except Exception as e:
        print("Error handling WebApp data:", e)

# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Command handler
    app.add_handler(CommandHandler("start", start))

    # WebApp data handler
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

    print("Bot is running...")
    app.run_polling()
