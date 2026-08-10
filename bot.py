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

# DATABASE SOZLAMALARI
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

def format_duration(seconds):
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins}:{secs:02d}"

def clean_url(url):
    clean = re.sub(r'\?.*$', '', url.strip())
    if not clean.endswith('/'):
        clean += '/'
    return clean

# INSTAGRAM VIDEO YUKLASH TIZIMI
def download_insta_video(url, output_path):
    c_url = clean_url(url)
    
    # 1. DDINSTAGRAM
    try:
        dd_url = c_url.replace("instagram.com", "ddinstagram.com")
        req = urllib.request.Request(dd_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8')
            video_match = re.search(r'<meta property="og:video" content="([^"]+)"', html)
            if video_match:
                video_url = video_match.group(1).replace('&amp;', '&')
                urllib.request.urlretrieve(video_url, output_path)
                if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    return True
    except Exception:
        pass

    # 2. YT_DLP
    try:
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'user_agent': 'Instagram 219.0.0.12.117 Android',
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([c_url])
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
    except Exception:
        pass

    return False

# INSTAGRAM/TIKTOK AUDIOSINI BEVOSITA YUKLASH
def download_insta_audio(url, output_path):
    c_url = clean_url(url)
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([c_url])
        return True
    except Exception:
        return False

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
        "✨ **InstaSave Bot-ga xush kelibsiz!** ✨\n\n"
        "🎬 Instagram/TikTok havolasini yuboring — video va audiosini yuklab beraman.\n"
        "🎵 Yoki qo'shiq nomini yozing — to'liq versiyasini topib beraman!"
    )
    bot.reply_to(message, welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@bot.message_handler(commands=['about', 'info'])
@bot.message_handler(func=lambda message: message.text == "ℹ️ Bot haqida va imkoniyatlar")
def send_about(message):
    add_user(message.chat.id, message.from_user.username)
    about_text = (
        "🤖 **Bot haqida ma'lumot:**\n\n"
        "Ushbu bot Instagram va TikTok ijtimoiy tarmoqlaridan videolarni "
        "tez va yuqori sifatda yuklash hamda to'liq musiqalarni qidirib topish uchun yaratilgan.\n\n"
        "👤 **Bot egasi:** Soliyev Davronbek\n"
        "🚀 **Versiya:** 3.4 Pro"
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

# SAQLASH TUGMASI HANDLERI
@bot.callback_query_handler(func=lambda call: call.data == "save_video")
def handle_save_video(call):
    try:
        bot.forward_message(chat_id=call.from_user.id, from_chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id, "✅ Video saqlandi!", show_alert=False)
    except Exception:
        bot.answer_callback_query(call.id, "❌ Saqlashda xatolik yuz berdi.", show_alert=True)

# VIDEODAN MUSIQA AJRATISH HANDLERI (XATOSIZ)
@bot.callback_query_handler(func=lambda call: call.data.startswith("get_audio_"))
def handle_get_audio(call):
    video_url = call.data.replace("get_audio_", "").replace("___", "/")
    bot.answer_callback_query(call.id, "🎵 Qo'shiq ajratib olinmoqda...")
    status_audio = bot.send_message(call.message.chat.id, "⏳ Audio tayyorlanmoqda...")

    temp_audio = f"audio_{call.message.message_id}.mp3"

    try:
        # Bevosita havola orqali yt-dlp yordamida audioni sifatli yuklab olish
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': temp_audio.replace('.mp3', ''),
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        if not os.path.exists(temp_audio):
            # Muqobil nom bilan qidirish
            alt_name = temp_audio.replace('.mp3', '') + ".mp3"
            if os.path.exists(alt_name):
                temp_audio = alt_name

        if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1000:
            bot_info = bot.get_me()
            inline_markup = types.InlineKeyboardMarkup()
            btn_group = types.InlineKeyboardButton("Guruhga qo'shish ⤴️", url=f"https://t.me/{bot_info.username}?startgroup=true")
            inline_markup.add(btn_group)

            with open(temp_audio, 'rb') as aud:
                bot.send_audio(
                    call.message.chat.id,
                    aud,
                    caption=f"📥 @{bot_info.username} orqali yuklab olindi",
                    reply_markup=inline_markup
                )
            log_download(call.message.chat.id, call.from_user.username, "Video Audiosi")
        else:
            bot.send_message(call.message.chat.id, "❌ Ushbu videoda audio trek topilmadi.")

    except Exception:
        bot.send_message(call.message.chat.id, "❌ Audioni ajratib olishda xatolik yuz berdi.")

    finally:
        try:
            bot.delete_message(chat_id=call.message.chat.id, message_id=status_audio.message_id)
        except Exception:
            pass
        if os.path.exists(temp_audio):
            os.remove(temp_audio)

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

    # 1. INSTAGRAM & TIKTOK VIDEO YUKLASH
    if "instagram.com" in text or "tiktok.com" in text:
        status_msg = bot.send_message(message.chat.id, "⏳ Video yuklanmoqda, kuting...")
        video_path = f"video_{message.message_id}.mp4"

        try:
            success = download_insta_video(text, video_path)

            if success and os.path.exists(video_path):
                bot_info = bot.get_me()
                inline_markup = types.InlineKeyboardMarkup(row_width=1)
                
                # Url variantini callback_data ichiga xavfsiz joylash
                safe_url = text.replace("/", "___")
                if len(safe_url) > 50:
                    safe_url = safe_url[:50]

                btn_save = types.InlineKeyboardButton("💾 Saqlash", callback_data="save_video")
                btn_audio = types.InlineKeyboardButton("📥 Qo'shiqni yuklab olish", callback_data=f"get_audio_{safe_url}")
                btn_group = types.InlineKeyboardButton("Guruhga qo'shish ⤴️", url=f"https://t.me/{bot_info.username}?startgroup=true")
                
                inline_markup.add(btn_save, btn_audio, btn_group)

                # Videoni yuborish
                with open(video_path, 'rb') as v:
                    bot.send_video(
                        message.chat.id,
                        v,
                        caption=f"📥 @{bot_info.username} orqali yuklab olindi",
                        reply_markup=inline_markup
                    )
                log_download(message.chat.id, message.from_user.username, f"Video: {text}")

                # MATNLI XABARNI MUVAFFAQIYATLI O'CHIRISH
                try:
                    bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
                except Exception:
                    pass

            else:
                bot.edit_message_text("❌ Videoni yuklab bo'lmadi. Link yopiq yoki o'chirilgan bo'lishi mumkin.", chat_id=message.chat.id, message_id=status_msg.message_id)

        except Exception:
            try:
                bot.edit_message_text("❌ Videoni yuklashda xatolik yuz berdi.", chat_id=message.chat.id, message_id=status_msg.message_id)
            except Exception:
                pass

        finally:
            if os.path.exists(video_path):
                os.remove(video_path)

    # 2. QO'SHIQ QIDIRUVI (DEEZER)
    else:
        status_msg = bot.send_message(message.chat.id, f"🔍 **{text}** qidirilmoqda...", parse_mode="Markdown")
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

            res_text = f"🎵 **Qidiruv natijalari:** `{text}`\n\n"
            inline_markup = types.InlineKeyboardMarkup(row_width=5)
            buttons = []

            for idx, track in enumerate(tracks, 1):
                artist = track['artist']['name']
                title = track['title']
                duration = format_duration(track['duration'])
                res_text += f"**{idx}.** {artist} — {title} `({duration})`\n"
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

# DEEZER MUSIQA YUKLASH TUGMASI
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
    preview_url = track['preview']

    bot.answer_callback_query(call.id, f"🎵 {title} yuklanmoqda...")
    status_msg = bot.send_message(chat_id, f"⏳ **{artist} — {title}** yuklanmoqda...")

    try:
        bot_info = bot.get_me()
        inline_markup = types.InlineKeyboardMarkup()
        btn_group = types.InlineKeyboardButton("Guruhga qo'shish ⤴️", url=f"https://t.me/{bot_info.username}?startgroup=true")
        inline_markup.add(btn_group)

        bot.send_audio(
            chat_id,
            preview_url,
            caption=f"🎵 **{artist} — {title}**\n\n🤖 Bot: InstaSave Bot",
            parse_mode="Markdown",
            reply_markup=inline_markup
        )
        log_download(chat_id, call.from_user.username, f"Qo'shiq: {artist} - {title}")
        
        try:
            bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        except Exception:
            pass

    except Exception:
        bot.send_message(chat_id, "❌ Qo'shiqni yuklab bo'lmadi.")

if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    print("Bot va Server muvaffaqiyatli ishga tushdi...")
    bot.infinity_polling()
