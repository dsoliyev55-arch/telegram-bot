import os
import re
import threading
from flask import Flask
import telebot
from telebot import types
from yt_dlp import YoutubeDL

# Render uchun web-server
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

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

def extract_shortcode(url):
    match = re.search(r'instagram\.com/(?:p|reel|reels|tv)/([^/?#&]+)', url)
    return match.group(1) if match else None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    add_user(message.chat.id)
    welcome_text = (
        "Salom! Menga Instagram havolasini yoki qo'shiq nomini yuboring.\n"
        "Men sizga video hamda musiqalarni topib beraman! 🎥🎵"
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
    text = message.text.strip()
    
    # 1. AGAR INSTAGRAM LINKI YUBORILSA
    if "instagram.com" in text:
        status_msg = bot.reply_to(message, "⏳ Video yuklanmoqda, kuting...")
        video_file = f"video_{message.message_id}.mp4"
        shortcode = extract_shortcode(text)

        try:
            ydl_opts = {
                'format': 'best',
                'outtmpl': video_file,
                'quiet': True,
                'no_warnings': True,
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                title = info.get('title', 'Instagram Video')

            bot.edit_message_text("⬆️ Telegram'ga yuklanmoqda...", chat_id=message.chat.id, message_id=status_msg.message_id)

            inline_markup = types.InlineKeyboardMarkup()
            if shortcode:
                btn_audio = types.InlineKeyboardButton("🎵 Qo'shiqni yuklab olish", callback_data=f"aud_{shortcode}")
                inline_markup.add(btn_audio)
            
            bot_info = bot.get_me()
            btn_group = types.InlineKeyboardButton("Guruhga qo'shish ⤴️", url=f"https://t.me/{bot_info.username}?startgroup=true")
            inline_markup.add(btn_group)

            if os.path.exists(video_file):
                with open(video_file, 'rb') as v:
                    bot.send_video(
                        message.chat.id, 
                        v, 
                        caption=f"🎬 {title}\n\n🤖 Bot: InstaSave Bot",
                        reply_markup=inline_markup
                    )

            bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)

        except Exception:
            bot.edit_message_text("❌ Hech narsa topilmadi.", chat_id=message.chat.id, message_id=status_msg.message_id)

        finally:
            if os.path.exists(video_file):
                os.remove(video_file)

    # 2. AGAR QO'SHIQ NOMI MATN SIFATIDA YUBORILSA
    else:
        status_msg = bot.reply_to(message, f"🔍 **{text}** musiqasi qidirilmoqda...", parse_mode="Markdown")
        audio_file = f"search_{message.message_id}.mp3"

        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': audio_file,
                'quiet': True,
                'no_warnings': True,
                'default_search': 'ytsearch1',
            }
            with YoutubeDL(ydl_opts) as ydl:
                yt_info = ydl.extract_info(f"ytsearch1:{text} audio", download=True)
                song_title = text
                if 'entries' in yt_info and len(yt_info['entries']) > 0:
                    song_title = yt_info['entries'][0].get('title', text)

            if os.path.exists(audio_file):
                with open(audio_file, 'rb') as a:
                    bot.send_audio(
                        message.chat.id,
                        a,
                        caption=f"🎵 **{song_title}**\n\n🤖 Bot: InstaSave Bot",
                        parse_mode="Markdown"
                    )
                bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
            else:
                bot.edit_message_text("❌ Hech narsa topilmadi.", chat_id=message.chat.id, message_id=status_msg.message_id)

        except Exception:
            bot.edit_message_text("❌ Hech narsa topilmadi.", chat_id=message.chat.id, message_id=status_msg.message_id)

        finally:
            if os.path.exists(audio_file):
                os.remove(audio_file)

# INLINE TUGMA UCHUN HANDLER
@bot.callback_query_handler(func=lambda call: call.data.startswith('aud_'))
def handle_audio_download(call):
    bot.answer_callback_query(call.id, "🎵 Audio ajratib olinmoqda...")
    shortcode = call.data.replace('aud_', '')
    insta_url = f"https://www.instagram.com/reel/{shortcode}/"
    
    status_msg = bot.send_message(call.message.chat.id, "⏳ Qo'shiq yuklanmoqda...")
    audio_file_pattern = f"audio_{call.message.message_id}"

    try:
        ydl_opts = {
            'format': 'm4a/bestaudio/best',
            'outtmpl': f"{audio_file_pattern}.%(ext)s",
            'quiet': True,
            'no_warnings': True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(insta_url, download=True)
            ext = info.get('ext', 'm4a')
            title = info.get('title', 'Instagram Audio')

        final_audio_path = f"{audio_file_pattern}.{ext}"

        if os.path.exists(final_audio_path):
            with open(final_audio_path, 'rb') as a:
                bot.send_audio(
                    call.message.chat.id,
                    a,
                    caption=f"🎵 **{title}**\n\n🤖 Bot: InstaSave Bot",
                    reply_to_message_id=call.message.message_id,
                    parse_mode="Markdown"
                )
            os.remove(final_audio_path)
            bot.delete_message(chat_id=call.message.chat.id, message_id=status_msg.message_id)
        else:
            bot.edit_message_text("❌ Hech narsa topilmadi.", chat_id=call.message.chat.id, message_id=status_msg.message_id)

    except Exception:
        bot.edit_message_text("❌ Hech narsa topilmadi.", chat_id=call.message.chat.id, message_id=status_msg.message_id)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Bot va Server ishga tushdi...")
    bot.infinity_polling()
