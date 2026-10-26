import os
import sqlite3
import random
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
import threading

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# 👉 ADMIN_ID CỦA BẠN
ADMIN_ID = "8661772753" 

def init_db():
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id TEXT PRIMARY KEY,
            casino_id TEXT UNIQUE,
            username TEXT,
            balance REAL DEFAULT 1705.00,
            is_frozen INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def is_admin(user_id: str) -> bool:
    return user_id == ADMIN_ID

def generate_casino_id(cursor):
    while True:
        new_id = str(random.randint(100000000, 999999999))
        cursor.execute("SELECT telegram_id FROM users WHERE casino_id = ?", (new_id,))
        if not cursor.fetchone():
            return new_id

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    user = update.effective_user
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else str(user.id)

    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute("SELECT casino_id, balance FROM users WHERE telegram_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        casino_id = generate_casino_id(cursor)
        balance = 1705.00
        cursor.execute(
            "INSERT INTO users (telegram_id, casino_id, username, balance, is_frozen) VALUES (?, ?, ?, ?, ?)",
            (user_id, casino_id, username, balance, 0)
        )
        conn.commit()
    else:
        casino_id = row[0]
        balance = row[1]
    conn.close()

    display_balance = "∞ (Vô tận)" if is_admin(user_id) else f"{balance} USDT"

    welcome_text = (
        "🤖 **CHÀO MỪNG ĐẾN VỚI SÒNG BÀI BACCARAT VIP** 🤖\n\n"
        "✨ Hệ thống bàn cược trực tuyến chuẩn quốc tế.\n"
        f"🆔 **ID của bạn:** `{casino_id}`\n"
        f"💰 **Số dư ví:** `{display_balance}`\n\n"
        "👇 Nhấn nút bên dưới để mở bàn chơi giao diện trực tiếp:"
    )
    
    # Lấy URL Web App tự động từ biến môi trường Render hoặc URL mặc định
    webapp_url = os.getenv("RENDER_EXTERNAL_URL", "https://your-app-name.onrender.com")
    
    keyboard = [[InlineKeyboardButton("🎰 VÀO BÀN BACCARAT (LIVE)", web_app=WebAppInfo(url=webapp_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    user = update.effective_user
    user_id = str(user.id)
    
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute("SELECT balance, is_frozen FROM users WHERE telegram_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO users (telegram_id, casino_id, username, balance, is_frozen) VALUES (?, ?, ?, ?, ?)", 
                       (user_id, generate_casino_id(cursor), f"@{user.username}" if user.username else user_id, 1708.00, 0))
        conn.commit()
        conn.close()
        await update.message.reply_text("🎁 Nhận thưởng thành công! Số dư ví đã được cộng thêm 3 USDT.")
        return

    balance, is_frozen = row[0], row[1]
    if is_frozen == 1:
        conn.close()
        await update.message.reply_text("❌ Tài khoản của bạn đang bị đóng băng.")
        return

    new_balance = balance + 3.0 if not is_admin(user_id) else balance
    cursor.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (new_balance, user_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🎁 Điểm danh thành công! Số dư hiện tại: {new_balance} USDT")

# FastAPI: Đọc file index.html phục vụ giao diện Web App
web_app = FastAPI()

@web_app.get("/", response_class=HTMLResponse)
def home():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Không tìm thấy file index.html trên hệ thống!</h3>"

def run_web():
    uvicorn.run(web_app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

if __name__ == '__main__':
    init_db()
    if not BOT_TOKEN:
        print("❌ Lỗi: Chưa cấu hình BOT_TOKEN!")
    else:
        web_thread = threading.Thread(target=run_web, daemon=True)
        web_thread.start()

        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("checkin", checkin_command))
        
        print("🤖 Bot Telegram tích hợp Baccarat Mini App đã khởi chạy thành công...")
        app.run_polling()
