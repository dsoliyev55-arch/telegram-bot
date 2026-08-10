import os
import re
import sqlite3
import threading
import urllib.parse
import urllib.request
import json
from datetime import datetime
from flask import Flask
import telebot
from telebot import types
from yt_dlp import YoutubeDL

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot status: ONLINE"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(TOKEN)
DB_NAME = "bot_data.db"
user_search_results = {}

# BAZA VA LOGLAR TABLE
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY, channel_url TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, content TEXT, created_at TEXT)''')
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    uname = f"@{username}" if username else "Mavjud emas"
    cursor.execute("INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)", (user_id, uname))
    conn.commit()
    conn.close()

def log_download(user_id, username, content):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    uname = f"@{username}" if username else "Mavjud emas"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO logs (user_id, username, content, created_at) VALUES (?, ?, ?, ?)", (user_id, uname, content, now))
    conn.commit()
    conn.close()

    # Admintga real-vaqt rejimida bildirgi yuborish
    if ADMIN_ID != 0:
        try:
            admin_msg = (
                f"📥 **Yangi yuklama!**\n\n"
                f"👤 **Foydalanuvchi:** {uname} (ID: `{user_id}`)\n"
                f"🎵/🎬 **Yukladi:** {content}\n"
                f"🕒 **Vaqt:** {now}"
            )
            bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
        except Exception:
            pass

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def get_channels():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, channel_url FROM channels")
    channels = cursor.fetchall()
    conn.close()
    return channels

def check_sub(user_id):
    channels = get_channels()
    unsubscribed = []
    for ch_id, ch_url in channels:
        try:
            member = bot.get_chat_member(ch_id, user_id)
            if member.status not in ['creator', 'administrator', 'member']:
                unsubscribed.append((ch_id, ch_url))
        except Exception:
            pass
    return unsubscribed

def get_sub_keyboard(unsub_list):
    markup = types.InlineKeyboardMarkup()
    for idx, (ch_id, ch_url) in enumerate(unsub_list, 1):
        btn = types.InlineKeyboardButton(f"📢 {idx}-kanalga a'zo bo'lish", url=ch_url)
        markup.add(btn)
    btn_check = types.InlineKeyboardButton("🔄 Tekshirish", callback_data="check_subscription")
    markup.add(btn_check)
    return markup

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_info = types.KeyboardButton("ℹ️ Bot haqida va imkoniyatlar")
    markup.add(btn_info)
    return markup

def extract_shortcode(url):
    match = re.search(r'instagram\.com/(?:p|reel|reels|tv)/([^/?#&]+)', url)
    return match.group(1) if match else None

def format_duration(seconds):
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins}:{secs:02d}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    add_user(message.chat.id, message.from_user.username)
    unsub = check_sub(message.chat.id)
    if unsub:
        bot.send_message(
            message.chat.id,
            "⚠️ **Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:**",
            parse_mode="Markdown",
            reply_markup=get_sub_keyboard(unsub)
        )
        return

    welcome_text = (
        "Salom! Menga Instagram/TikTok havolasini yoki qo'shiq nomini yuboring.\n"
        "Men sizga video hamda to'liq musiqalarni topib beraman! 🎥🎵"
    )
    bot.reply_to(message, welcome_text, reply_markup=get_main_keyboard())

# ADMIN BUYRUQLARI
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        return
    admin_text = (
        "🛠 **Admin Panel Buyruqlari:**\n\n"
        "📊 `/stat` - Foydalanuvchilar soni\n"
        "📜 `/logs` - Oxirgi yuklangan 10 ta media tarixi\n"
        "📢 `/rek` - Reklama tarqatish (Reply qilib)\n"
        "➕ `/add_channel @username link` - Obuna kanali qo'shish\n"
        "➖ `/del_channel @username` - Kanalni o'chirish"
    )
    bot.reply_to(message, admin_text, parse_mode="Markdown")

@bot.message_handler(commands=['stat'])
def send_stats(message):
    if message.chat.id != ADMIN_ID:
        return
    users = get_all_users()
    bot.reply_to(message, f"📊 Botingizda **{len(users)}** ta foydalanuvchi bor!", parse_mode="Markdown")

@bot.message_handler(commands=['logs'])
def send_logs(message):
    if message.chat.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username, content, created_at FROM logs ORDER BY id DESC LIMIT 10")
    logs = cursor.fetchall()
    conn.close()

    if not logs:
        bot.reply_to(message, "📜 Hozircha yuklamalar tarixi yo'q.")
        return

    text = "📜 **Oxirgi 10 ta yuklama tarixi:**\n\n"
    for uname, content, dt in logs:
        text += f"👤 {uname}\n📥 {content}\n🕒 {dt}\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    bot.reply_to(message, text)

@bot.message_handler(commands=['about', 'info'])
@bot.message_handler(func=lambda message: message.text == "ℹ️ Bot haqida va imkoniyatlar")
def send_about(message):
    add_user(message.chat.id, message.from_user.username)
    about_text = (
        "🤖 **Bot haqida ma'lumot:**\n\n"
        "Ushbu bot Instagram va TikTok ijtimoiy tarmoqlaridan videolarni "
        "tez va oson yuklash hamda to'liq musiqalarni qidirib topish uchun yaratilgan.\n\n"
        "👤 **Bot egasi:** Soliyev Davronbek\n"
        "🚀 **Versiya:** 2.4 Pro"
    )
    bot.reply_to(message, about_text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def cb_check_sub(call):
    unsub = check_sub(call.message.chat.id)
    if unsub:
        bot.answer_callback_query(call.id, "❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
    else:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "✅ Obuna tasdiqlandi! Endi botdan to'liq foydalanishingiz mumkin.", reply_markup=get_main_keyboard())

# ASOSIY MESSAGES HANDLER
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    add_user(message.chat.id, message.from_user.username)

    unsub = check_sub(message.chat.id)
    if unsub:
        bot.send_message(
            message.chat.id,
            "⚠️ **Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:**",
            parse_mode="Markdown",
            reply_markup=get_sub_keyboard(unsub)
        )
        return

    text = message.text.strip()

    # 1. INSTAGRAM VA TIKTOK VIDEO YUKLASH
    if "instagram.com" in text or "tiktok.com" in text:
        status_msg = bot.reply_to(message, "⏳ Video yuklanmoqda, kuting...")
        video_file = f"video_{message.message_id}.mp4"
        shortcode = extract_shortcode(text) if "instagram.com" in text else None

        try:
            ydl_opts = {
                'format': 'best',
                'outtmpl': video_file,
                'quiet': True,
                'no_warnings': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                }
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                title = info.get('title', 'Video')

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
                # LOG YOZISH VA ADMINGA XABAR
                log_download(message.chat.id, message.from_user.username, f"Video: {text}")

        except Exception:
            bot.send_message(message.chat.id, "❌ Video yuklab bo'lmadi.")

        finally:
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
            except Exception:
                pass
            if os.path.exists(video_file):
                os.remove(video_file)

    # 2. QO'SHIQ QIDIRUVI (DEEZER)
    else:
        status_msg = bot.reply_to(message, f"🔍 **{text}** qidirilmoqda...", parse_mode="Markdown")
        try:
            query = urllib.parse.quote(text)
            url = f"https://api.deezer.com/search?q={query}&limit=5"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())

            tracks = data.get('data', [])

            if not tracks:
                bot.edit_message_text("❌ Musiqa topilmadi.", chat_id=message.chat.id, message_id=status_msg.message_id)
                return

            user_search_results[message.chat.id] = tracks

            res_text = f"🎵 **{text}**\n\n"
            inline_markup = types.InlineKeyboardMarkup(row_width=5)
            buttons = []

            for idx, track in enumerate(tracks, 1):
                artist = track['artist']['name']
                title = track['title']
                duration = format_duration(track['duration'])
                res_text += f"**{idx}.** {artist} — {title} **{duration}**\n"
                buttons.append(types.InlineKeyboardButton(str(idx), callback_data=f"dz_{idx-1}"))

            inline_markup.add(*buttons)

            bot.edit_message_text(
                res_text,
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
                parse_mode="Markdown",
                reply_markup=inline_markup
            )

        except Exception:
            bot.edit_message_text("❌ Qidiruvda xatolik yuz berdi.", chat_id=message.chat.id, message_id=status_msg.message_id)

# 1,2,3,4,5 TUGMASI BOSILGANDA (TO'LIQ AUDIO YUKLASH)
@bot.callback_query_handler(func=lambda call: call.data.startswith('dz_'))
def handle_deezer_download(call):
    chat_id = call.message.chat.id
    idx = int(call.data.replace('dz_', ''))

    if chat_id not in user_search_results or idx >= len(user_search_results[chat_id]):
        bot.answer_callback_query(call.id, "❌ Qidiruv muddati o'tgan, qayta qidiring.")
        return

    track = user_search_results[chat_id][idx]
    artist = track['artist']['name']
    title = track['title']
    search_query = f"{artist} {title}"

    bot.answer_callback_query(call.id, f"🎵 {title} yuklanmoqda...")
    status_msg = bot.send_message(chat_id, f"⏳ **{artist} — {title}** yuklanmoqda...")

    audio_file_base = f"audio_{call.message.message_id}"

    try:
        ydl_opts = {
            'format': 'm4a/bestaudio/best',
            'outtmpl': f"{audio_file_base}.%(ext)s",
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch1',
            'nocheckcertificate': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web']
                }
            }
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"ytsearch1:{search_query} audio"])

        downloaded_file = None
        for file in os.listdir('.'):
            if file.startswith(audio_file_base):
                downloaded_file = file
                break

        bot_info = bot.get_me()
        inline_markup = types.InlineKeyboardMarkup()
        btn_group = types.InlineKeyboardButton("Guruhga qo'shish ⤴️", url=f"https://t.me/{bot_info.username}?startgroup=true")
        inline_markup.add(btn_group)

        if downloaded_file and os.path.exists(downloaded_file):
            with open(downloaded_file, 'rb') as a:
                bot.send_audio(
                    chat_id,
                    a,
                    caption=f"🎵 **{artist} — {title}**\n\n🤖 Bot: InstaSave Bot",
                    parse_mode="Markdown",
                    reply_markup=inline_markup
                )
            os.remove(downloaded_file)
            # LOG YOZISH VA ADMINGA XABAR
            log_download(chat_id, call.from_user.username, f"Qo'shiq: {artist} - {title}")
        else:
            bot.send_message(chat_id, "❌ Qo'shiq fayli topilmadi.")

    except Exception:
        bot.send_message(chat_id, "❌ Qo'shiqni yuklashda xatolik yuz berdi.")

    finally:
        try:
            bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        except Exception:
            pass

if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    print("Bot va Server muvaffaqiyatli ishga tushdi...")
    bot.infinity_polling()
