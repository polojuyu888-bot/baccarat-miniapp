import os
import sqlite3
import random
import logging
from datetime import datetime
from telegram import Update
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
            balance REAL DEFAULT 0,
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

# FastAPI: Giao diện Mini App Baccarat chuyên nghiệp độc quyền nội bộ
web_app = FastAPI()

@web_app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Baccarat Live Casino</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { background-color: #8b0000; color: #fff; font-family: Arial, sans-serif; margin: 0; padding: 0; user-select: none; }
            .header { background: #111; padding: 10px 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #d4af37; }
            .balance-box { background: #222; padding: 5px 12px; border-radius: 20px; border: 1px solid #d4af37; color: #d4af37; font-weight: bold; font-size: 14px; }
            .table-container { background: #0b6623; border: 6px solid #d4af37; border-radius: 15px; margin: 10px; padding: 15px; box-shadow: inset 0 0 20px rgba(0,0,0,0.6); text-align: center; }
            .bet-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px; }
            .bet-btn { padding: 20px; font-size: 18px; font-weight: bold; border-radius: 10px; border: none; cursor: pointer; color: white; text-transform: uppercase; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
            .btn-player { background: #1e3a8a; border: 2px solid #60a5fa; }
            .btn-banker { background: #991b1b; border: 2px solid #f87171; }
            .btn-tie { background: #14532d; border: 2px solid #4ade80; grid-column: span 2; padding: 12px; }
            .chip-container { display: flex; justify-content: center; gap: 10px; margin: 15px 0; }
            .chip { width: 45px; height: 45px; border-radius: 50%; background: #d4af37; color: #000; font-weight: bold; display: flex; align-items: center; justify-content: center; border: 3px dashed #fff; cursor: pointer; font-size: 12px; }
            .chip.active { border-style: solid; transform: scale(1.1); box-shadow: 0 0 10px #ff0; }
            .roadmap { background: #1a1a1a; border-radius: 8px; margin: 10px; padding: 10px; height: 80px; display: flex; gap: 5px; overflow-x: auto; align-items: center; border: 1px solid #444; }
            .road-item { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; flex-shrink: 0; }
            .road-P { background: #3b82f6; color: #fff; }
            .road-B { background: #ef4444; color: #fff; }
            .road-T { background: #22c55e; color: #fff; }
        </style>
    </head>
    <body>
        <div class="header">
            <span style="font-weight: bold; color: #d4af37;">👑 VIP BACCARAT TABLE 1</span>
            <div class="balance-box">💰 <span id="user-balance">0.00</span> USDT</div>
        </div>

        <div class="roadmap" id="roadmap">
            <div class="road-item road-B">庄</div>
            <div class="road-item road-P">闲</div>
            <div class="road-item road-P">闲</div>
            <div class="road-item road-B">庄</div>
            <div class="road-item road-T">和</div>
            <div class="road-item road-B">庄</div>
        </div>

        <div class="table-container">
            <h3 style="margin: 0 0 10px 0; color: #ffd700; text-shadow: 1px 1px 2px #000;">请 投 注 (PLACE YOUR BETS)</h3>
            <div style="font-size: 13px; color: #e2e8f0; margin-bottom: 10px;">当前选中筹码: <b id="selected-chip" style="color: #ffd700;">10 USDT</b></div>
            
            <div class="chip-container">
                <div class="chip active" onclick="selectChip(1, this)">1</div>
                <div class="chip" onclick="selectChip(5, this)">5</div>
                <div class="chip" onclick="selectChip(10, this)" style="background: #3b82f6; color:#fff;">10</div>
                <div class="chip" onclick="selectChip(50, this)" style="background: #9333ea; color:#fff;">50</div>
                <div class="chip" onclick="selectChip(100, this)" style="background: #ef4444; color:#fff;">100</div>
            </div>

            <div class="bet-grid">
                <button class="bet-btn btn-player" onclick="placeBet('PLAYER')">
                    闲 (PLAYER)<br><span style="font-size: 12px; font-weight: normal;">1 : 1</span>
                </button>
                <button class="bet-btn btn-banker" onclick="placeBet('BANKER')">
                    庄 (BANKER)<br><span style="font-size: 12px; font-weight: normal;">1 : 0.95</span>
                </button>
                <button class="bet-btn btn-tie" onclick="placeBet('TIE')">
                    和 (TIE) — 1 : 8
                </button>
            </div>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();

            let currentChip = 10;
            let balance = 100.0; // Sẽ đồng bộ dữ liệu thực tế từ Bot

            function selectChip(amount, element) {
                document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
                element.classList.add('active');
                currentChip = amount;
                document.getElementById('selected-chip').innerText = amount + ' USDT';
            }

            function placeBet(type) {
                alert('成功下注 ' + currentChip + ' USDT 选 ' + type);
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

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
