import os
import sqlite3
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Lấy Token bảo mật từ biến môi trường trên Render
BOT_TOKEN = os.getenv("8823333396:AAEQ0_wPDeR9tS9iqbJgS4zShtuMX9Xey60")

# 👉 HÃY THAY DÃY SỐ DƯỚI ĐÂY BẰNG ADMIN ID THẬT CỦA BẠN (Lấy từ @userinfobot)
ADMIN_ID = "8661772753" 

def init_db():
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            is_frozen INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# Hàm kiểm tra quyền Admin
def is_admin(user_id: str) -> bool:
    return user_id == ADMIN_ID

# 1. Điểm danh nhận 20 xu hằng ngày (Dành cho tất cả người chơi)
async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    user_id = str(update.effective_user.id)
    
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance, is_frozen FROM users WHERE telegram_id = ?", (user_id,))
    row = cursor.fetchone()

    if row and row[1] == 1:
        conn.close()
        await update.message.reply_text("❌ Tài khoản của bạn đang bị **đóng băng (frozen)**, không thể điểm danh hay giao dịch!", parse_mode="Markdown")
        return

    if not row:
        cursor.execute("INSERT INTO users (telegram_id, balance, is_frozen) VALUES (?, ?, ?)", (user_id, 20, 0))
        msg = "🎁 Chào mừng bạn đến với Sòng bài! Bạn nhận được **20 Xu** quà khởi nghiệp điểm danh ngày đầu tiên."
    else:
        cursor.execute("UPDATE users SET balance = balance + 20 WHERE telegram_id = ?", (user_id,))
        msg = "🎁 Điểm danh thành công! Bạn nhận được **20 Xu** vào tài khoản."

    conn.commit()
    conn.close()

    await update.message.reply_text(msg, parse_mode="Markdown")

# 2. Cộng xu (/add) - CHỈ ADMIN MỚI ĐƯỢC DÙNG
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này! Chỉ Quản trị viên mới được thao tác.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("⚠️ **Cách dùng:** `/add <telegram_id> <số_xu>`", parse_mode="Markdown")
        return

    target_id = context.args[0]
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Số xu phải là một con số nguyên hợp lệ!")
        return

    init_db()
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (target_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO users (telegram_id, balance, is_frozen) VALUES (?, ?, ?)", (target_id, amount, 0))
    else:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (amount, target_id))

    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ Đã cộng thành công **{amount} Xu** cho tài khoản ID: `{target_id}`!", parse_mode="Markdown")

# 3. Trừ xu phạt vi phạm (/sub) - CHỈ ADMIN MỚI ĐƯỢC DÙNG
async def sub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này! Chỉ Quản trị viên mới được thao tác.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("⚠️ **Cách dùng:** `/sub <telegram_id> <số_xu>`", parse_mode="Markdown")
        return

    target_id = context.args[0]
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Số xu phải là một con số nguyên hợp lệ!")
        return

    init_db()
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (target_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO users (telegram_id, balance, is_frozen) VALUES (?, ?, ?)", (target_id, -amount, 0))
    else:
        cursor.execute("UPDATE users SET balance = balance - ? WHERE telegram_id = ?", (amount, target_id))

    conn.commit()
    conn.close()

    await update.message.reply_text(f"⚖️ Đã phạt trừ **{amount} Xu** của tài khoản ID: `{target_id}` do vi phạm nội quy!", parse_mode="Markdown")

# 4. Đóng băng tài sản (/freeze) - CHỈ ADMIN MỚI ĐƯỢC DÙNG
async def freeze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này! Chỉ Quản trị viên mới được thao tác.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ **Cách dùng:** `/freeze <telegram_id>`", parse_mode="Markdown")
        return

    target_id = context.args[0]
    init_db()
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()

    cursor.execute("SELECT balance, is_frozen FROM users WHERE telegram_id = ?", (target_id,))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text(f"⚠️ Không tìm thấy tài khoản ID: `{target_id}` trong hệ thống!", parse_mode="Markdown")
        conn.close()
        return

    cursor.execute("UPDATE users SET is_frozen = 1 WHERE telegram_id = ?", (target_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"❄️ Đã **đóng băng (frozen)** thành công tài khoản ID: `{target_id}`! Điểm số được giữ nguyên nhưng người chơi bị khóa quyền giao dịch.", parse_mode="Markdown")

# 5. Mở băng tài sản (/unfreeze) - CHỈ ADMIN MỚI ĐƯỢC DÙNG
async def unfreeze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này! Chỉ Quản trị viên mới được thao tác.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ **Cách dùng:** `/unfreeze <telegram_id>`", parse_mode="Markdown")
        return

    target_id = context.args[0]
    init_db()
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()

    cursor.execute("SELECT balance, is_frozen FROM users WHERE telegram_id = ?", (target_id,))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text(f"⚠️ Không tìm thấy tài khoản ID: `{target_id}` trong hệ thống!", parse_mode="Markdown")
        conn.close()
        return

    cursor.execute("UPDATE users SET is_frozen = 0 WHERE telegram_id = ?", (target_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"🔥 Đã **mở băng (unfrozen)** thành công cho tài khoản ID: `{target_id}`! Người chơi đã hoạt động trở lại bình thường.", parse_mode="Markdown")

if __name__ == '__main__':
    init_db()
    if not BOT_TOKEN:
        print("❌ Lỗi: Chưa cấu hình BOT_TOKEN trên môi trường!")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # Đăng ký các câu lệnh quản lý
        app.add_handler(CommandHandler("checkin", checkin_command))
        app.add_handler(CommandHandler("add", add_command))
        app.add_handler(CommandHandler("sub", sub_command))
        app.add_handler(CommandHandler("freeze", freeze_command))
        app.add_handler(CommandHandler("unfreeze", unfreeze_command))
        
        print("🤖 Bot quản lý sòng bài với quyền Admin đã sẵn sàng...")
        app.run_polling()
