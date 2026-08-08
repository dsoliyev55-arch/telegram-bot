import os
import telebot
from telebot import types
from yt_dlp import YoutubeDL

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_info = types.KeyboardButton("ℹ️ Bot haqida")
    markup.add(btn_info)
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "Salom! Menga Instagram Reels yoki post havolasini yuboring.\n"
        "Men sizga videoni va undagi musiqani yuklab beraman! 🎥🎵"
    )
    bot.reply_to(message, welcome_text, reply_markup=get_main_keyboard())

@bot.message_handler(commands=['about', 'info'])
@bot.message_handler(func=lambda message: message.text == "ℹ️ Bot haqida")
def send_about(message):
    about_text = (
        "🤖 Bot haqida ma'lumot:\n\n"
        "Ushbu bot Instagram ijtimoiy tarmog'idan videolarni va "
        "ularning ichidagi musiqalarni tez hamda qulay yuklab olish uchun yaratilgan.\n\n"
        "👤 Bot egasi: Soliyev Davronbek\n"
        "🚀 Versiya: 1.0"
    )
    bot.reply_to(message, about_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()
    
    if "instagram.com" not in url:
        bot.reply_to(message, "Iltimos, to'g'ri Instagram havolasini yuboring!")
        return

    status_msg = bot.reply_to(message, "⏳ Video va audio yuklanmoqda, kuting...")

    video_file = f"video_{message.message_id}.mp4"
    audio_file = f"audio_{message.message_id}.mp3"

    try:
        ydl_opts_video = {
            'format': 'mp4/best',
            'outtmpl': video_file,
            'quiet': True,
            'no_warnings': True,
        }
        with YoutubeDL(ydl_opts_video) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Instagram Video')

        ydl_opts_audio = {
            'format': 'bestaudio/best',
            'outtmpl': audio_file,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }
        with YoutubeDL(ydl_opts_audio) as ydl:
            ydl.download([url])

        bot.edit_message_text("⬆️ Telegram'ga yuklanmoqda...", chat_id=message.chat.id, message_id=status_msg.message_id)

        if os.path.exists(video_file):
            with open(video_file, 'rb') as v:
                bot.send_video(message.chat.id, v, caption=f"🎬 {title}\n\n👤 Ega: Soliyev Davronbek")

        if os.path.exists(audio_file):
            with open(audio_file, 'rb') as a:
                bot.send_audio(message.chat.id, a, caption=f"🎵 Video ichidagi musiqa\n\n👤 Ega: Soliyev Davronbek")

        bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik yuz berdi yoki video topilmadi.\n{str(e)}", chat_id=message.chat.id, message_id=status_msg.message_id)

    finally:
        if os.path.exists(video_file):
            os.remove(video_file)
        if os.path.exists(audio_file):
            os.remove(audio_file)

if __name__ == "__main__":
    print("Bot ishga tushdi...")
    bot.infinity_polling()
