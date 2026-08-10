import os
import re
import sqlite3
import threading
import urllib.parse
import urllib.request
import json
from flask import Flask
import telebot
from telebot import types
from yt_dlp import YoutubeDL

# Render uchun Web Server
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot status: ONLINE"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# SOZLAMALAR (Environment Variables orqali olinadi)
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # O'zingizning Telegram ID'ingiz

bot = telebot.TeleBot(TOKEN)
DB_NAME = "bot_data.db"
user_search_results = {}

# MA'LUMOTLAR BAZASI (SQLite)
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY, channel_url TEXT)''')
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

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

def add_channel(channel_id, channel_url):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO channels (channel_id, channel_url) VALUES (?, ?)", (str(channel_id), channel_url))
    conn.commit()
    conn.close()

def delete_channel(channel_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE channel_id = ?", (str(channel_id),))
    conn.commit()
    conn.close()

# MAJBURiY OBUNANI TEKSHIRISH
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

# START COMMAND
@bot.message_handler(commands=['start'])
def send_welcome(message):
    add_user(message.chat.id)
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

# ADMIN PANEL COMMANDS
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        return
    admin_text = (
        "🛠 **Admin Panel Commands:**\n\n"
        "📊 `/stat` - Barcha foydalanuvchilar soni\n"
        "📢 `/rek` - Reklama tarqatish (Xabarga reply qilib yozing)\n"
        "➕ `/add_channel @kanal_username link` - Majburiy obuna qo'shish\n"
        "➖ `/del_channel @kanal_username` - Kanalni o'chirish\n"
        "📜 `/list_channels` - Ulangan kanallar ro'yxati"
    )
    bot.reply_to(message, admin_text, parse_mode="Markdown")

@bot.message_handler(commands=['stat'])
def send_stats(message):
    users = get_all_users()
    bot.reply_to(message, f"📊 Botingizda **{len(users)}** ta foydalanuvchi bor!", parse_mode="Markdown")

@bot.message_handler(commands=['add_channel'])
def add_ch_cmd(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        ch_id = parts[1]
        ch_url = parts[2]
        add_channel(ch_id, ch_url)
        bot.reply_to(message, f"✅ Kanal qo'shildi: {ch_id}")
    except Exception:
        bot.reply_to(message, "❌ Noto'g'ri format. Ishlatish: `/add_channel @username https://t.me/...`", parse_mode="Markdown")

@bot.message_handler(commands=['del_channel'])
def del_ch_cmd(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        ch_id = parts[1]
        delete_channel(ch_id)
        bot.reply_to(message, f"🗑 Kanal o'chirildi: {ch_id}")
    except Exception:
        bot.reply_to(message, "❌ Noto'g'ri format. Ishlatish: `/del_channel @username`", parse_mode="Markdown")

@bot.message_handler(commands=['list_channels'])
def list_ch_cmd(message):
    if message.chat.id != ADMIN_ID:
        return
    channels = get_channels()
    if not channels:
        bot.reply_to(message, "📜 Hozircha majburiy obuna kanallari yo'q.")
        return
    text = "📜 **Majburiy obunadagi kanallar:**\n\n"
    for ch_id, ch_url in channels:
        text += f"• {ch_id} -> {ch_url}\n"
    bot.reply_to(message, text, parse_mode="Markdown")

# REKLAMA TARQATISH (`/rek` REPLAY QILIB ISHLATILADI)
@bot.message_handler(commands=['rek'])
def broadcast_ad(message):
    if message.chat.id != ADMIN_ID:
        return
    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ Reklama yuborish uchun biror bir xabarga **reply** qilib `/rek` deb yozing.")
        return

    users = get_all_users()
    success = 0
    failed = 0
    status_msg = bot.send_message(ADMIN_ID, f"📢 Reklama yuborilmoqda... (0/{len(users)})")

    for user_id in users:
        try:
            bot.copy_message(chat_id=user_id, from_chat_id=ADMIN_ID, message_id=message.reply_to_message.message_id)
            success += 1
        except Exception:
            failed += 1

    bot.edit_message_text(
        f"✅ **Reklama yakunlandi!**\n\nYuborildi: {success} ta\nYetib bormadi (bloklagan): {failed} ta",
        chat_id=ADMIN_ID,
        message_id=status_msg.message_id,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['about', 'info'])
@bot.message_handler(func=lambda message: message.text == "ℹ️ Bot haqida va imkoniyatlar")
def send_about(message):
    add_user(message.chat.id)
    about_text = (
        "🤖 **Bot haqida ma'lumot:**\n\n"
        "Ushbu bot Instagram va TikTok ijtimoiy tarmoqlaridan videolarni "
        "tez va oson yuklash hamda to'liq musiqalarni qidirib topish uchun yaratilgan.\n\n"
        "👤 **Bot egasi:** Soliyev Davronbek\n"
        "🚀 **Versiya:** 2.0 Pro"
    )
    bot.reply_to(message, about_text, parse_mode="Markdown")

# OBUNANI TEKSHIRISH CALLBACK
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
    add_user(message.chat.id)

    # Obunani tekshirish
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

    # 1. INSTAGRAM SOBIQA TIKTOK LINKLARI
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
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                title = info.get('title', 'Video')

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

    # 2. QO'SHIQ QIDIRUVI (DEEZER -> YOUTUBE FULL SONG)
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
                bot.edit_message_text("❌ Hech narsa topilmadi.", chat_id=message.chat.id, message_id=status_msg.message_id)
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
            bot.edit_message_text("❌ Hech narsa topilmadi.", chat_id=message.chat.id, message_id=status_msg.message_id)

# 1,2,3,4,5 TUGMASI BOSILGANDA FULL AUDIO YUKLASH
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
    search_query = f"{artist} - {title}"

    bot.answer_callback_query(call.id, f"🎵 {title} yuklanmoqda...")
    status_msg = bot.send_message(chat_id, f"⏳ **{search_query}** to'liq yuklanmoqda...")

    audio_file = f"full_{call.message.message_id}.mp3"

    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': audio_file,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch1',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios']
                }
            }
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(f"ytsearch1:{search_query} full audio", download=True)

        bot_info = bot.get_me()
        inline_markup = types.InlineKeyboardMarkup()
        btn_group = types.InlineKeyboardButton("Guruhga qo'shish ⤴️", url=f"https://t.me/{bot_info.username}?startgroup=true")
        inline_markup.add(btn_group)

        if os.path.exists(audio_file):
            with open(audio_file, 'rb') as a:
                bot.send_audio(
                    chat_id,
                    a,
                    caption=f"🎵 **{artist} — {title}**\n\n🤖 Bot: InstaSave Bot",
                    parse_mode="Markdown",
                    reply_markup=inline_markup
                )
            bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        else:
            bot.edit_message_text("❌ Hech narsa topilmadi.", chat_id=chat_id, message_id=status_msg.message_id)

    except Exception:
        bot.edit_message_text("❌ Hech narsa topilmadi.", chat_id=chat_id, message_id=status_msg.message_id)

    finally:
        if os.path.exists(audio_file):
            os.remove(audio_file)

# INSTAGRAM REELS AUDIOSINI YUKLASH
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
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    print("Bot va Server muvaffaqiyatli ishga tushdi...")
    bot.infinity_polling()
