from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

# Get bot token from environment variable (GitHub secret)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN environment variable not found!")

# Your web app URL
WEB_APP_URL = os.environ.get("WEB_APP_URL")
if not WEB_APP_URL:
    raise Exception("WEB_APP_URL environment variable not found!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Inline button to launch web app
    keyboard = [
        [InlineKeyboardButton("Launch App", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send banner image with caption
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=open("banner.png", "rb"),  # Ensure banner.png is in the same folder
        caption="Welcome to TokenHatch! 🥚\nHatch creatures, get $EGG crypto points, and earn airdrops!",
        reply_markup=reply_markup
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    print("Bot started...")
    app.run_polling()
