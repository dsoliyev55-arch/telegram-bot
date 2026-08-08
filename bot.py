import os
import telebot
from telebot import types
from yt_dlp import YoutubeDL

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Foydalanuvchilar ID'sini faylga saqlash
USER_FILE = "users.txt"

def add_user(user_id):
    users = set()
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            users = set(f.read().splitlines())
    if str(user_id) not in users:
        with open(USER_FILE, "a") as f:
            f.write(f"{user_id}\n")

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_info = types.KeyboardButton("ℹ️ Bot haqida va imkoniyatlar")
    markup.add(btn_info)
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    add_user(message.chat.id)
    welcome_text = (
        "Salom! Menga Instagram Reels yoki post havolasini yuboring.\n"
        "Men sizga videoni yuklab beraman! 🎥🎵"
    )
    bot.reply_to(message, welcome_text, reply_markup=get_main_keyboard())

@bot.message_handler(commands=['stat'])
def send_stats(message):
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            users = f.read().splitlines()
        count = len(users)
        bot.reply_to(message, f"📊 Botingizdan **{count}** ta foydalanuvchi foydalanmoqda!", parse_mode="Markdown")
    else:
        bot.reply_to(message, "📊 Hozircha foydalanuvchilar soni: 0")

@bot.message_handler(commands=['about', 'info'])
@bot.message_handler(func=lambda message: message.text == "ℹ️ Bot haqida va imkoniyatlar")
def send_about(message):
    add_user(message.chat.id)
    about_text = (
        "🤖 **Bot haqida ma'lumot:**\n\n"
        "Ushbu bot Instagram ijtimoiy tarmog'idan videolarni "
        "tez hamda qulay yuklab olish uchun yaratilgan.\n\n"
        "👤 **Bot egasi:** Soliyev Davronbek\n"
        "🚀 **Versiya:** 1.0"
    )
    bot.reply_to(message, about_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    add_user(message.chat.id)
    url = message.text.strip()
    
    if "instagram.com" not in url:
        bot.reply_to(message, "Iltimos, to'g'ri Instagram havolasini yuboring!")
        return

    status_msg = bot.reply_to(message, "⏳ Video yuklanmoqda, kuting...")
    video_file = f"video_{message.message_id}.mp4"

    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': video_file,
            'quiet': True,
            'no_warnings': True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Instagram Video')

        bot.edit_message_text("⬆️ Telegram'ga yuklanmoqda...", chat_id=message.chat.id, message_id=status_msg.message_id)

        if os.path.exists(video_file):
            with open(video_file, 'rb') as v:
                bot.send_video(message.chat.id, v, caption=f"🎬 {title}\n\n👤 Ega: Soliyev Davronbek\n🤖 Bot: InstaSave Bot")

        bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik yuz berdi yoki video topilmadi.\n{str(e)}", chat_id=message.chat.id, message_id=status_msg.message_id)

    finally:
        if os.path.exists(video_file):
            os.remove(video_file)

if __name__ == "__main__":
    print("Bot ishga tushdi...")
    bot.infinity_polling()
