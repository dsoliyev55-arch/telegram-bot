import os
import telebot

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Salom! Bot Render'da muvaffaqiyatli ishlayapti! 🚀")

if __name__ == "__main__":
    print("Bot ishga tushdi...")
    bot.infinity_polling()

