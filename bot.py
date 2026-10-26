import os
import sqlite3
import random
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from fastapi import FastAPI
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
            balance REAL DEFAULT 0,
            is_frozen INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def is_admin(user_id: str) -> bool:
    return user_id == ADMIN_ID

# Hàm sinh ngẫu nhiên mã ID sòng bài gồm 9 chữ số
def generate_casino_id(cursor):
    while True:
        new_id = str(random.randint(100000000, 999999999))
        cursor.execute("SELECT telegram_id FROM users WHERE casino_id = ?", (new_id,))
        if not cursor.fetchone():
            return new_id

# 0. Lệnh /start chào mừng và cấp ID 9 chữ số ngẫu nhiên (Số dư mặc định 0 cho người mới)
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
        balance = 0.0
        cursor.execute(
            "INSERT INTO users (telegram_id, casino_id, username, balance, is_frozen) VALUES (?, ?, ?, ?, ?)",
            (user_id, casino_id, username, balance, 0)
        )
        conn.commit()
    else:
        casino_id = row[0]
        balance = row[1]
        cursor.execute("UPDATE users SET username = ? WHERE telegram_id = ?", (username, user_id))
        conn.commit()

    conn.close()

    # Nếu là Admin hiển thị vô cực, người chơi thường hiển thị đúng số dư thực tế trong DB
    display_balance = "∞ (Vô tận)" if is_admin(user_id) else f"{balance} USDT"

    welcome_text = (
        "🤖 **CHÀO MỪNG ĐẾN VỚI SÒNG BÀI BACCARAT** 🤖\n\n"
        "✨ Hệ thống giải trí và quản lý tài sản USDT tự động.\n"
        f"🆔 **ID của bạn:** `{casino_id}`\n"
        f"💰 **Số dư ví:** `{display_balance}`\n\n"
        "🎁 Sử dụng lệnh `/checkin` mỗi ngày để nhận thưởng khởi nghiệp nhé!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# Lệnh tra cứu ID của người chơi dành cho Admin (/id @username)
async def get_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = str(update.effective_user.id)
    if not is_admin(admin_id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này!")
        return

    if not context.args:
        await update.message.reply_text("⚠️ **Cách dùng:** `/id <@username>`", parse_mode="Markdown")
        return

    target = context.args[0]
    init_db()
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()

    cursor.execute("SELECT casino_id, telegram_id, balance FROM users WHERE username = ? OR telegram_id = ?", (target, target))
    row = cursor.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(f"⚠️ Không tìm thấy người chơi `{target}` trong hệ thống!", parse_mode="Markdown")
        return

    casino_id, tg_id, balance = row[0], row[1], row[2]
    
    display_balance = "∞ (Vô tận)" if is_admin(tg_id) else f"{balance} USDT"

    await update.message.reply_text(
        f"🔍 **THÔNG TIN TÀI KHOẢN TRA CỨU**\n\n"
        f"👤 Tài khoản: `{target}`\n"
        f"🆔 **Mã ID 9 số:** `{casino_id}`\n"
        f"📱 Telegram ID: `{tg_id}`\n"
        f"💰 Số dư ví: `{display_balance}`",
        parse_mode="Markdown"
    )

# 1. Điểm danh nhận thưởng USDT hằng ngày (Mỗi ngày 3 USDT)
async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    user = update.effective_user
    user_id = str(user.id)
    
    if is_admin(user_id):
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await update.message.reply_text(f"您于 {now_time} 成功获得签到奖励 3 USDT，现钱包余额 ∞ (Vô tận) USDT")
        return

    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance, is_frozen, casino_id FROM users WHERE telegram_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        casino_id = generate_casino_id(cursor)
        cursor.execute("INSERT INTO users (telegram_id, casino_id, username, balance, is_frozen) VALUES (?, ?, ?, ?, ?)", 
                       (user_id, casino_id, f"@{user.username}" if user.username else user_id, 3.0, 0))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"🎁 Chào mừng! Bạn được cấp ID `{casino_id}` và nhận **3 USDT** điểm danh ngày đầu tiên.", parse_mode="Markdown")
        return

    balance, is_frozen, casino_id = row[0], row[1], row[2]

    if is_frozen == 1:
        conn.close()
        await update.message.reply_text(
            "🚨 **CẢNH BÁO HỆ THỐNG** 🚨\n\n"
            "❌ Tài khoản của bạn hiện đang bị **đóng băng** do có quyết định xử lý từ Quản trị viên.\n"
            "🔒 Mọi giao dịch, điểm danh và hoạt động đặt cược đều bị từ chối.",
            parse_mode="Markdown"
        )
        return

    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_balance = balance + 3.0
    cursor.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (new_balance, user_id))
    conn.commit()
    conn.close()

    msg = f"您于 {now_time} 成功获得签到奖励 3 USDT，现钱包余额 {new_balance} USDT"
    await update.message.reply_text(msg)

# 2. Cộng USDT bằng Mã ID 9 số
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = str(update.effective_user.id)
    if not is_admin(admin_id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này!")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("⚠️ **Cách dùng:** `/add <ID_9_số> <số_USDT>`", parse_mode="Markdown")
        return

    casino_id = context.args[0]
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Số tiền phải là một con số hợp lệ!")
        return

    init_db()
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT telegram_id, balance FROM users WHERE casino_id = ?", (casino_id,))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text(f"⚠️ Không tìm thấy người chơi có Mã ID `{casino_id}` trong hệ thống!", parse_mode="Markdown")
        conn.close()
        return

    target_telegram_id = row[0]
    old_balance = row[1]
    
    current_balance = "∞ (Vô tận)" if is_admin(target_telegram_id) else old_balance + amount
    
    if not is_admin(target_telegram_id):
        cursor.execute("UPDATE users SET balance = ? WHERE casino_id = ?", (current_balance, casino_id))
    
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ Đã cộng thành công **{amount} USDT** cho tài khoản ID: `{casino_id}`!", parse_mode="Markdown")

    try:
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bal_text = "∞" if is_admin(target_telegram_id) else current_balance
        notify_text = f"您于 {now_time} 成功存款 {amount} USDT，现钱包余额 {bal_text} USDT"
        await context.bot.send_message(chat_id=target_telegram_id, text=notify_text)
    except Exception as e:
        print(f"Không thể gửi tin nhắn cho user: {e}")

# 3. Trừ USDT bằng Mã ID 9 số
async def sub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = str(update.effective_user.id)
    if not is_admin(admin_id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này!")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("⚠️ **Cách dùng:** `/sub <ID_9_số> <số_USDT>`", parse_mode="Markdown")
        return

    casino_id = context.args[0]
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Số tiền phải là một con số hợp lệ!")
        return

    init_db()
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT telegram_id, balance FROM users WHERE casino_id = ?", (casino_id,))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text(f"⚠️ Không tìm thấy người chơi có Mã ID `{casino_id}` trong hệ thống!", parse_mode="Markdown")
        conn.close()
        return

    target_telegram_id = row[0]
    old_balance = row[1]
    
    current_balance = "∞ (Vô tận)" if is_admin(target_telegram_id) else max(0.0, old_balance - amount)
    
    if not is_admin(target_telegram_id):
        cursor.execute("UPDATE users SET balance = ? WHERE casino_id = ?", (current_balance, casino_id))
    
    conn.commit()
    conn.close()

    await update.message.reply_text(f"⚖️ Đã trừ **{amount} USDT** của tài khoản ID: `{casino_id}`!", parse_mode="Markdown")

    try:
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bal_text = "∞" if is_admin(target_telegram_id) else current_balance
        notify_text = f"您于 {now_time} 成功取款 {amount} USDT，现钱包余额 {bal_text} USDT"
        await context.bot.send_message(chat_id=target_telegram_id, text=notify_text)
    except Exception as e:
        print(f"Không thể gửi tin nhắn cho user: {e}")

# 4. Đóng băng tài sản
async def freeze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = str(update.effective_user.id)
    if not is_admin(admin_id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này!")
        return

    if not context.args:
        await update.message.reply_text("⚠️ **Cách dùng:** `/freeze <ID_9_số>`", parse_mode="Markdown")
        return

    casino_id = context.args[0]
    init_db()
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()

    cursor.execute("SELECT telegram_id FROM users WHERE casino_id = ?", (casino_id,))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text(f"⚠️ Không tìm thấy tài khoản có Mã ID `{casino_id}`!", parse_mode="Markdown")
        conn.close()
        return

    target_telegram_id = row[0]
    if is_admin(target_telegram_id):
        await update.message.reply_text("⛔ Không thể đóng băng tài khoản Quản trị viên tối cao!")
        conn.close()
        return

    cursor.execute("UPDATE users SET is_frozen = 1 WHERE casino_id = ?", (casino_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"❄️ Đã **đóng băng** tài khoản ID: `{casino_id}` thành công!", parse_mode="Markdown")

# 5. Mở băng tài sản
async def unfreeze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = str(update.effective_user.id)
    if not is_admin(admin_id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này!")
        return

    if not context.args:
        await update.message.reply_text("⚠️ **Cách dùng:** `/unfreeze <ID_9_số>`", parse_mode="Markdown")
        return

    casino_id = context.args[0]
    init_db()
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()

    cursor.execute("SELECT telegram_id FROM users WHERE casino_id = ?", (casino_id,))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text(f"⚠️ Không tìm thấy tài khoản có Mã ID `{casino_id}`!", parse_mode="Markdown")
        conn.close()
        return

    target_telegram_id = row[0]
    cursor.execute("UPDATE users SET is_frozen = 0 WHERE casino_id = ?", (casino_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"🔥 Đã **mở băng** tài khoản ID: `{casino_id}` thành công!", parse_mode="Markdown")
    
    try:
        await context.bot.send_message(
            chat_id=target_telegram_id, 
            text="🔥 **THÔNG BÁO HỆ THỐNG:** Tài khoản của bạn đã được Quản trị viên **mở băng**!", 
            parse_mode="Markdown"
        )
    except:
        pass

# Web App chạy ngầm giữ kết nối cho UptimeRobot
web_app = FastAPI()

@web_app.get("/")
def home():
    return {"status": "Bot is active!"}

def run_web():
    uvicorn.run(web_app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

if __name__ == '__main__':
    init_db()
    if not BOT_TOKEN:
        print("❌ Lỗi: Chưa cấu hình BOT_TOKEN trên môi trường!")
    else:
        web_thread = threading.Thread(target=run_web, daemon=True)
        web_thread.start()

        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("id", get_id_command))
        app.add_handler(CommandHandler("checkin", checkin_command))
        app.add_handler(CommandHandler("add", add_command))
        app.add_handler(CommandHandler("sub", sub_command))
        app.add_handler(CommandHandler("freeze", freeze_command))
        app.add_handler(CommandHandler("unfreeze", unfreeze_command))
        
        print("🤖 Bot quản lý sòng bài với quyền Admin vô cực đã sẵn sàng...")
        app.run_polling()
