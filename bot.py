from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import os
import sqlite3
import json

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = "https://tokenhatch.onrender.com/?v=2"

# --- SQLite database setup ---
conn = sqlite3.connect("tokens.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_tokens (
    user_id INTEGER PRIMARY KEY,
    tokens INTEGER DEFAULT 0
)
""")
conn.commit()

# --- Helper functions ---
def get_tokens(user_id: int) -> int:
    cursor.execute("SELECT tokens FROM user_tokens WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0

def set_tokens(user_id: int, tokens: int):
    cursor.execute("""
    INSERT INTO user_tokens (user_id, tokens) VALUES (?, ?)
    ON CONFLICT(user_id) DO UPDATE SET tokens = excluded.tokens
    """, (user_id, tokens))
    conn.commit()

# --- /start command ---
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

# --- Handle data sent from the Web App ---
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.web_app_data:
        user_id = update.effective_user.id
        data_str = update.message.web_app_data.data
        try:
            data = json.loads(data_str)
            tokens = int(data.get("tokens", 0))
            set_tokens(user_id, tokens)
            await update.message.reply_text(f"✅ Your tokens have been saved! Current: {tokens}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error saving data: {e}")

# --- Retrieve user tokens ---
async def my_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tokens = get_tokens(user_id)
    await update.message.reply_text(f"💰 You currently have {tokens} $EGG tokens!")

# --- Main ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mytokens", my_tokens))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.run_polling()
