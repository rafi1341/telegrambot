import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Bot token from BotFather
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# URL where Telegram should send updates (Netlify, Cloudflare Tunnel, or your domain)
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://your-domain.com/" + BOT_TOKEN)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    keyboard = [
        [InlineKeyboardButton("Launch App", web_app=WebAppInfo(url="https://tokenhatch.netlify.app/"))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_photo(
        chat_id=chat_id,
        photo=open("banner.png", "rb"),
        caption="Welcome to TokenHatch! 🥚\nHatch creatures, get $EGG crypto points, and earn airdrops!",
        reply_markup=reply_markup
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    print("Bot started with webhook...")

    # Run webhook server
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8443)),
        webhook_url=WEBHOOK_URL
    )
