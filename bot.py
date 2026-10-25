import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("8823333396:AAHVJoEAm1-zZEzEI8Oigk8HRK9JrAGqOLg")

# 👉 HÃY THAY DÃY SỐ NÀY BẰNG ADMIN ID THẬT CỦA BẠN (Lấy từ @userinfobot)
ADMIN_ID = "8661772753" 

def init_db():
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id TEXT PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            is_frozen INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def is_admin(user_id: str) -> bool:
    return user_id == ADMIN_ID

# 1. Điểm danh nhận thưởng USDT hằng ngày (Có kiểm tra trạng thái đóng băng)
async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    user = update.effective_user
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else str(user.id)
    
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance, is_frozen FROM users WHERE telegram_id = ?", (user_id,))
    row = cursor.fetchone()

    # Kịch bản cảnh báo trực tiếp khi tài khoản bị đóng băng mà cố tình thao tác
    if row and row[1] == 1:
        conn.close()
        await update.message.reply_text(
            "🚨 **CẢNH BÁO HỆ THỐNG** 🚨\n\n"
            "❌ Tài khoản của bạn hiện đang bị **đóng băng** do có quyết định xử lý từ Quản trị viên.\n"
            "🔒 Mọi giao dịch, điểm danh và hoạt động đặt cược đều bị từ chối.\n"
            "📞 Vui lòng liên hệ trực tiếp với Quản trị viên để được hỗ trợ giải quyết.",
            parse_mode="Markdown"
        )
        return

    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not row:
        new_balance = 20.0
        cursor.execute("INSERT INTO users (telegram_id, username, balance, is_frozen) VALUES (?, ?, ?, ?)", (user_id, username, new_balance, 0))
    else:
        new_balance = row[0] + 20.0
        cursor.execute("UPDATE users SET balance = balance + 20.0, username = ? WHERE telegram_id = ?", (username, user_id))

    conn.commit()
    conn.close()

    # Mẫu thông báo điểm danh giữ nguyên đơn vị USDT
    msg = f"您于 {now_time} 成功获得签到奖励 20 USDT，现钱包余额 {new_balance} USDT"
    await update.message.reply_text(msg)

# 2. Cộng USDT (/add) kèm thông báo tài chính
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = str(update.effective_user.id)
    if not is_admin(admin_id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này!")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("⚠️ **Cách dùng:** `/add <telegram_id hoặc @username> <số_USDT>`", parse_mode="Markdown")
        return

    target = context.args[0]
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Số tiền phải là một con số hợp lệ!")
        return

    init_db()
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT telegram_id, balance FROM users WHERE telegram_id = ? OR username = ?", (target, target))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text(f"⚠️ Không tìm thấy người chơi `{target}` trong hệ thống database!", parse_mode="Markdown")
        conn.close()
        return

    target_telegram_id = row[0]
    current_balance = row[1] + amount
    
    cursor.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (current_balance, target_telegram_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ Đã cộng thành công **{amount} USDT** cho tài khoản `{target}`!", parse_mode="Markdown")

    # Gửi tin nhắn riêng cho người chơi chuẩn mẫu USDT của bạn
    try:
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notify_text = f"您于 {now_time} 成功存款 {amount} USDT，现钱包余额 {current_balance} USDT"
        await context.bot.send_message(chat_id=target_telegram_id, text=notify_text)
    except Exception as e:
        print(f"Không thể gửi tin nhắn cho user: {e}")

# 3. Trừ USDT (/sub) kèm thông báo tài chính
async def sub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = str(update.effective_user.id)
    if not is_admin(admin_id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này!")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("⚠️ **Cách dùng:** `/sub <telegram_id hoặc @username> <số_USDT>`", parse_mode="Markdown")
        return

    target = context.args[0]
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Số tiền phải là một con số hợp lệ!")
        return

    init_db()
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT telegram_id, balance FROM users WHERE telegram_id = ? OR username = ?", (target, target))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text(f"⚠️ Không tìm thấy người chơi `{target}` trong hệ thống database!", parse_mode="Markdown")
        conn.close()
        return

    target_telegram_id = row[0]
    current_balance = max(0.0, row[1] - amount)
    
    cursor.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (current_balance, target_telegram_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"⚖️ Đã trừ **{amount} USDT** của tài khoản `{target}`!", parse_mode="Markdown")

    # Gửi tin nhắn riêng cho người chơi chuẩn mẫu USDT của bạn
    try:
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notify_text = f"您于 {now_time} 成功取款 {amount} USDT，现钱包余额 {current_balance} USDT"
        await context.bot.send_message(chat_id=target_telegram_id, text=notify_text)
    except Exception as e:
        print(f"Không thể gửi tin nhắn cho user: {e}")

# 4. Đóng băng tài sản (/freeze) - Không gửi thông báo, giữ nguyên số dư
async def freeze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = str(update.effective_user.id)
    if not is_admin(admin_id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này!")
        return

    if not context.args:
        await update.message.reply_text("⚠️ **Cách dùng:** `/freeze <telegram_id hoặc @username>`", parse_mode="Markdown")
        return

    target = context.args[0]
    init_db()
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()

    cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = ? OR username = ?", (target, target))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text(f"⚠️ Không tìm thấy tài khoản `{target}`!", parse_mode="Markdown")
        conn.close()
        return

    target_telegram_id = row[0]
    cursor.execute("UPDATE users SET is_frozen = 1 WHERE telegram_id = ?", (target_telegram_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"❄️ Đã **đóng băng** tài khoản `{target}` thành công! Số dư USDT được bảo lưu nhưng người chơi sẽ nhận cảnh báo khi cố tình thao tác.", parse_mode="Markdown")

# 5. Mở băng tài sản (/unfreeze)
async def unfreeze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = str(update.effective_user.id)
    if not is_admin(admin_id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này!")
        return

    if not context.args:
        await update.message.reply_text("⚠️ **Cách dùng:** `/unfreeze <telegram_id hoặc @username>`", parse_mode="Markdown")
        return

    target = context.args[0]
    init_db()
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()

    cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = ? OR username = ?", (target, target))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text(f"⚠️ Không tìm thấy tài khoản `{target}`!", parse_mode="Markdown")
        conn.close()
        return

    target_telegram_id = row[0]
    cursor.execute("UPDATE users SET is_frozen = 0 WHERE telegram_id = ?", (target_telegram_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"🔥 Đã **mở băng** tài khoản `{target}` thành công! Người chơi đã hoạt động trở lại bình thường.", parse_mode="Markdown")
    
    try:
        await context.bot.send_message(
            chat_id=target_telegram_id, 
            text="🔥 **THÔNG BÁO HỆ THỐNG:** Tài khoản của bạn đã được Quản trị viên **mở băng**, bạn có thể tiếp tục giao dịch bình thường!", 
            parse_mode="Markdown"
        )
    except:
        pass

if __name__ == '__main__':
    init_db()
    if not BOT_TOKEN:
        print("❌ Lỗi: Chưa cấu hình BOT_TOKEN trên môi trường!")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        app.add_handler(CommandHandler("checkin", checkin_command))
        app.add_handler(CommandHandler("add", add_command))
        app.add_handler(CommandHandler("sub", sub_command))
        app.add_handler(CommandHandler("freeze", freeze_command))
        app.add_handler(CommandHandler("unfreeze", unfreeze_command))
        
        print("🤖 Bot quản lý sòng bài chuẩn USDT đã sẵn sàng...")
        app.run_polling()
