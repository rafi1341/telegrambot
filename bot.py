from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import threading

# --------- Configuration ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Store tokens in memory for now (replace with DB later if needed)
user_tokens = {}  # key: user_id (str), value: tokens (int)

# --------- Flask API ----------
app = Flask(__name__)

@app.route("/get_tokens", methods=["GET"])
def get_tokens():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    tokens = user_tokens.get(user_id, 0)
    return jsonify({"tokens": tokens})

@app.route("/update_tokens", methods=["POST"])
def update_tokens():
    data = request.json
    user_id = data.get("user_id")
    tokens = data.get("tokens")
    if user_id is None or tokens is None:
        return jsonify({"error": "user_id and tokens required"}), 400
    user_tokens[user_id] = tokens
    return jsonify({"success": True})

# --------- Telegram Bot ----------
WEB_APP_URL = "https://tokenhatch.onrender.com/?v=2"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    keyboard = [
        [InlineKeyboardButton("Launch App💵", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_photo(
        chat_id=chat_id,
        photo=open("banner.png", "rb"),
        caption="Welcome to TokenHatch! 🥚 Hatch creatures, get $EGG crypto points, and earn airdrops!",
        reply_markup=reply_markup
    )

# Run Flask in a separate thread
def run_flask():
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()

    # Telegram Bot
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.run_polling()
