import os
import logging
import sqlite3
import random  # <-- QO'SHILDI: Tasodifiy stiker tanlash uchun
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode # <-- QO'SHILDI: HTML uchun kerak
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# ------------------- KONFIGURATSIYA -------------------
load_dotenv()

TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')
ADMIN_ID = int(os.getenv('ADMIN_ID', '123456789'))

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

# --- QO'SHILDI: Bot javob berishdan oldin yuboradigan stikerlar ro'yxati ---
# Bu stikerlarning ID'larini @idstickerbot orqali olishingiz mumkin
# @idstickerbot dan olingan yangi ID'lar
STICKER_LIST = [
    'CAACAgIAAxkBAAEKYMtk8p7iB32RzRBC5L4AAQ4dqeuvWpYAAmQAA66n8UsG7883d1OOHzAE'  # <- @idstickerbot'dan olgan ISHONCHLI bitta ID'ingizni shu yerga qo'ying
]

# ------------------- LOGGING -------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ------------------- MA'LUMOTLAR BAZASI (O'zgarishsiz qoldirildi) -------------------
def init_database():
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, username TEXT,
        first_name TEXT, message_text TEXT NOT NULL, is_bot BOOLEAN DEFAULT 0, created_at TEXT NOT NULL
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, last_seen TEXT
    )''')
    conn.commit()
    conn.close()

def save_message(user: dict, message: str, is_bot=False):
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_seen)
    VALUES (?, ?, ?, ?, ?)
    ''', (user['id'], user.get('username'), user.get('first_name'), user.get('last_name'), datetime.now().isoformat()))
    cursor.execute('''
    INSERT INTO messages (user_id, username, first_name, message_text, is_bot, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (user['id'], user.get('username'), user.get('first_name'), message, int(is_bot), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM messages WHERE user_id = ?', (user_id,))
    total_messages = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM messages WHERE user_id = ? AND is_bot = 0', (user_id,))
    user_messages = cursor.fetchone()[0]
    cursor.execute('SELECT created_at FROM messages WHERE user_id = ? ORDER BY created_at DESC LIMIT 1', (user_id,))
    last_active = cursor.fetchone()
    conn.close()
    return {'total_messages': total_messages, 'user_messages': user_messages, 'last_active': last_active[0] if last_active else "Noma'lum"}

# ------------------- BOT FUNKSIYALARI (O'zgarishsiz qoldirildi) -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = {'id': user.id, 'username': user.username, 'first_name': user.first_name, 'last_name': user.last_name}
    save_message(user_data, "/start komandasi")
    await update.message.reply_sticker(sticker=random.choice(STICKER_LIST)) # <-- QO'SHILDI: salomlashish stikeri
    await update.message.reply_html(
        rf"👋 Salom {user.mention_html()}! Men MakhmudX AI Suniy Intelektman. "
        "Menga yozing istalgan savolingizga javob bera olaman!\n\n"
        "📌 <b>Foydalanish uchun qo'llanma:</b>\n"
        "/start - Botni qayta ishga tushirish\n"
        "/stats - Shaxsiy statistika\n"
        "/help - Yordam olish"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = {'id': update.effective_user.id, 'username': update.effective_user.username, 'first_name': update.effective_user.first_name}
    save_message(user, "/help komandasi")
    help_text = ("🤖 <b>Yordam menyusi</b>\n\n"
                 "Menga istalgan savolingizni yuboring va men sizga javob beraman!\n\n"
                 "📌 <b>Mavjud komandalar:</b>\n"
                 "/start - Bot bilan ishni boshlash\n"
                 "/stats - Shaxsiy statistika\n"
                 "/help - Ushbu yordam xabari\n\n"
                 "💡 <b>Namunalar:</b>\n"
                 "• Pythonda kod yozish\n"
                 "• Tarix haqida savollar\n"
                 "• Tarjima qilish")
    await update.message.reply_html(help_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = {'id': user.id, 'username': user.username, 'first_name': user.first_name}
    save_message(user_data, "/stats komandasi")
    stats = get_user_stats(user.id)
    stats_text = (f"📊 <b>Shaxsiy statistika</b>\n\n"
                  f"👤 Foydalanuvchi: {user.first_name}\n"
                  f"📨 Jami xabarlar: {stats['total_messages']}\n"
                  f"📤 Sizning xabarlaringiz: {stats['user_messages']}\n"
                  f"⏳ So'ngi faollik: {stats['last_active']}")
    await update.message.reply_html(stats_text)


# ------------------- ASOSIY XABARLARNI QAYTA ISHLASH FUNKSIYASI (YANGILANDI) -------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    user_data = {'id': user.id, 'username': user.username, 'first_name': user.first_name, 'last_name': user.last_name}
    save_message(user_data, message_text)

    # Foydalanuvchiga kutayotganini bildirish uchun stiker va "typing" statusini yuborish
    await context.bot.send_sticker(chat_id=update.effective_chat.id, sticker=random.choice(STICKER_LIST))
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    try:
        # Gemini uchun yangilangan so'rov. Endi undan HTML formatlashni so'raymiz.
        prompt = (
            "Siz foydalanuvchiga yordam beradigan, o'zbek tilida gaplashadigan aqlli yordamchisiz. "
            "Javobni chiroyli va tushunarli formatlash uchun oddiy HTML teglardan foydalan "
            "(masalan, <b>qalin matn</b>, <i>kursiv matn</i>, <u>tagi chizilgan</u>, "
            "<code>bitta qator kod</code>, va <pre>ko'p qatorli kod yoki matn bloki</pre>). "
            f"Foydalanuvchining savoli: {message_text}"
        )

        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.7, "max_output_tokens": 3000}
        )
        ai_response = response.text
        save_message(user_data, ai_response, is_bot=True)

        # Javobni HTML sifatida yuborish
        await update.message.reply_html(ai_response)

    except Exception as e:
        logger.error(f"Xato yuz berdi: {str(e)}")
        await update.message.reply_text("⚠️ Kechirasiz, javob berishda xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.")


# ------------------- ASOSIY DASTUR -------------------
def main():
    init_database()
    if not TOKEN:
        logger.error("TELEGRAM_TOKEN topilmadi! .env faylini yoki server sozlamalarini tekshiring.")
        return
    if not GEMINI_KEY:
        logger.error("GEMINI_API_KEY topilmadi! .env faylini yoki server sozlamalarini tekshiring.")
        return

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot ishga tushmoqda...")
    application.run_polling()

if __name__ == '__main__':
    main()