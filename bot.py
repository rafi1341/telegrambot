from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Replace with your actual bot token from BotFather
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Replace with your Netlify app URL
WEB_APP_URL = "https://tokenhatch.onrender.com/"

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
        photo=open("banner.png", "rb"),  # Make sure banner.png is in the same folder
        caption="Welcome to TokenHatch! 🥚\nHatch creatures, get $EGG crypto points, and earn airdrops!",
        reply_markup=reply_markup
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    print("Bot started...")
    app.run_polling()
