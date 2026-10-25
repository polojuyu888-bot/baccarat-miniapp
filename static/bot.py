import os
import sqlite3
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Lấy Token bảo mật từ biến môi trường trên Render
BOT_TOKEN = os.getenv("8823333396:AAEQ0_wPDeR9tS9iqbJgS4zShtuMX9Xey60")

def init_db():
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute("INSERT INTO users (telegram_id, balance) VALUES (?, ?)", (user_id, 20))
        msg = "🎉 Chào mừng bạn đến với Sòng bài! Bạn nhận được **20 Xu** quà khởi nghiệp điểm danh ngày đầu tiên."
    else:
        cursor.execute("UPDATE users SET balance = balance + 20 WHERE telegram_id = ?", (user_id,))
        msg = "🎁 Điểm danh thành công! Bạn nhận được **+20 Xu** vào tài khoản."
        
    conn.commit()
    conn.close()
    
    await update.message.reply_text(msg, parse_mode="Markdown")

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("❌ Lỗi: Chưa cấu hình BOT_TOKEN trên môi trường!")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("checkin", checkin_command))
        print("🤖 Bot Telegram đang chạy trên Cloud...")
        app.run_polling()
