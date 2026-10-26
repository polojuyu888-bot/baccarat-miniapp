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

# FastAPI: Giao diện Mini App Baccarat với bàn chơi Live Dealer mô phỏng sắc nét
web_app = FastAPI()

@web_app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Live Baccarat Casino</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { background-color: #0d0f12; color: #fff; font-family: Arial, sans-serif; margin: 0; padding: 0; user-select: none; }
            
            /* Khung Live mô phỏng trực quan sòng bài */
            .live-container { position: relative; width: 100%; height: 210px; background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%); border-bottom: 2px solid #d4af37; display: flex; flex-direction: column; align-items: center; justify-content: center; overflow: hidden; }
            .live-badge { position: absolute; top: 10px; left: 10px; background: rgba(220, 38, 38, 0.9); color: white; padding: 3px 8px; font-size: 11px; font-weight: bold; border-radius: 4px; display: flex; align-items: center; gap: 4px; z-index: 10; }
            .live-badge::before { content: ''; width: 6px; height: 6px; background: #fff; border-radius: 50%; animation: blink 1s infinite; }
            @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.2; } 100% { opacity: 1; } }
            
            /* Bàn bài chia Live Dealer */
            .dealer-table { display: flex; width: 90%; justify-content: space-around; align-items: center; margin-top: 15px; }
            .cards-box { background: rgba(0,0,0,0.5); border: 1px solid #334155; border-radius: 8px; padding: 8px; width: 42%; text-align: center; }
            .p-title { font-weight: bold; font-size: 13px; margin-bottom: 5px; }
            .cards-flex { display: flex; justify-content: center; gap: 5px; }
            .card { width: 32px; height: 46px; background: #fff; color: #000; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.5); }
            .card.red { color: #dc2626; }
            .score-badge { display: inline-block; background: #d4af37; color: #000; font-size: 11px; font-weight: bold; padding: 2px 6px; border-radius: 10px; margin-top: 4px; }

            .table-info { position: absolute; bottom: 6px; left: 10px; font-size: 11px; color: #94a3b8; }

            /* Bàn cược chính */
            .betting-board { background: #580000; padding: 10px; }
            
            /* Lưới cược phụ */
            .side-bets-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; margin-bottom: 8px; }
            .side-bet-card { background: rgba(0, 0, 0, 0.4); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 4px; padding: 6px 2px; text-align: center; cursor: pointer; }
            .side-bet-card:active { background: rgba(255, 215, 0, 0.3); }
            .sb-title { font-size: 11px; font-weight: bold; color: #fde047; }
            .sb-odds { font-size: 10px; color: #cbd5e1; }

            /* Cửa chính 闲, 和, 庄 */
            .main-bets-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; margin-bottom: 10px; }
            .main-bet-btn { padding: 12px 4px; border-radius: 6px; border: none; font-weight: bold; text-align: center; cursor: pointer; color: white; }
            .btn-player { background: #1d4ed8; border: 1px solid #60a5fa; }
            .btn-tie { background: #15803d; border: 1px solid #4ade80; }
            .btn-banker { background: #b91c1c; border: 1px solid #f87171; }

            /* Thanh chọn Chip phía dưới */
            .chip-bar { background: #111827; padding: 10px; display: flex; justify-content: space-around; align-items: center; border-top: 1px solid #1f2937; position: sticky; bottom: 0; }
            .chip { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; cursor: pointer; border: 2px dashed #fff; }
            .chip.active { border-style: solid; border-color: #ffd700; transform: scale(1.15); box-shadow: 0 0 8px #ffd700; }
            .chip-1 { background: #e2e8f0; color: #000; }
            .chip-5 { background: #3b82f6; color: #fff; }
            .chip-10 { background: #22c55e; color: #fff; }
            .chip-50 { background: #a855f7; color: #fff; }
            .chip-100 { background: #ef4444; color: #fff; }

            /* Roadmap (Bảng cầu) */
            .roadmap-bar { background: #111; padding: 6px 10px; display: flex; align-items: center; gap: 6px; overflow-x: auto; border-bottom: 1px solid #222; }
            .road-ball { width: 20px; height: 20px; border-radius: 50%; font-size: 10px; font-weight: bold; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
            .r-banker { background: #ef4444; color: white; }
            .r-player { background: #3b82f6; color: white; }
            .r-tie { background: #22c55e; color: white; }
        </style>
    </head>
    <body>

        <!-- 1. Màn hình Live Dealer mô phỏng trực quan -->
        <div class="live-container">
            <div class="live-badge">LIVE 8G.COM</div>
            
            <div class="dealer-table">
                <!-- Bài 闲 Player -->
                <div class="cards-box">
                    <div class="p-title" style="color: #60a5fa;">闲 (PLAYER)</div>
                    <div class="cards-flex">
                        <div class="card red">A ♥</div>
                        <div class="card">A ♣</div>
                    </div>
                    <div class="score-badge">2 点</div>
                </div>

                <!-- Bài 庄 Banker -->
                <div class="cards-box">
                    <div class="p-title" style="color: #f87171;">庄 (BANKER)</div>
                    <div class="cards-flex">
                        <div class="card red">9 ♦</div>
                        <div class="card">10 ♠</div>
                    </div>
                    <div class="score-badge">9 点</div>
                </div>
            </div>

            <div class="table-info">桌号: GB282692348E | 限红: 20-200,000</div>
        </div>

        <!-- 2. Bảng cầu (Roadmap) -->
        <div class="roadmap-bar">
            <span style="font-size: 11px; color: #94a3b8; font-weight: bold;">路单:</span>
            <div class="road-ball r-banker">庄</div>
            <div class="road-ball r-banker">庄</div>
            <div class="road-ball r-player">闲</div>
            <div class="road-ball r-banker">庄</div>
            <div class="road-ball r-tie">和</div>
            <div class="road-ball r-player">闲</div>
            <div class="road-ball r-banker">庄</div>
        </div>

        <!-- 3. Khu vực đặt cược đầy đủ chi tiết -->
        <div class="betting-board">
            
            <!-- Cửa cược phụ -->
            <div class="side-bets-grid">
                <div class="side-bet-card" onclick="placeBet('闲对 (Player Pair)')">
                    <div class="sb-title">闲对</div>
                    <div class="sb-odds">1 : 11</div>
                </div>
                <div class="side-bet-card" onclick="placeBet('幸运七 (Lucky 7)')">
                    <div class="sb-title">幸运七</div>
                    <div class="sb-odds">1 : 6 ~ 15</div>
                </div>
                <div class="side-bet-card" onclick="placeBet('超级幸运七 (Super Lucky 7)')">
                    <div class="sb-title">超级幸运七</div>
                    <div class="sb-odds">最高 1:100</div>
                </div>
                <div class="side-bet-card" onclick="placeBet('幸运六 (Lucky 6)')">
                    <div class="sb-title">幸运六</div>
                    <div class="sb-odds">1 : 12 ~ 20</div>
                </div>
            </div>

            <!-- Cửa cược chính -->
            <div class="main-bets-grid">
                <button class="main-bet-btn btn-player" onclick="placeBet('闲 (PLAYER)')">
                    <div>闲 (PLAYER)</div>
                    <div>1 : 1</div>
                </button>
                <button class="main-bet-btn btn-tie" onclick="placeBet('和 (TIE)')">
                    <div>和 (TIE)</div>
                    <div>1 : 8</div>
                </button>
                <button class="main-bet-btn btn-banker" onclick="placeBet('庄 (BANKER)')">
                    <div>庄 (BANKER)</div>
                    <div>1 : 0.95</div>
                </button>
            </div>
        </div>

        <!-- 4. Thanh chọn Chip -->
        <div class="chip-bar">
            <span style="font-size: 12px; color: #fbbf24; font-weight: bold;">筹码: <span id="chip-val">10</span></span>
            <div class="chip chip-1" onclick="selectChip(1, this)">1</div>
            <div class="chip chip-5" onclick="selectChip(5, this)">5</div>
            <div class="chip chip-10 active" onclick="selectChip(10, this)">10</div>
            <div class="chip chip-50" onclick="selectChip(50, this)">50</div>
            <div class="chip chip-100" onclick="selectChip(100, this)">100</div>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();

            let currentChip = 10;

            function selectChip(amount, element) {
                document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
                element.classList.add('active');
                currentChip = amount;
                document.getElementById('chip-val').innerText = amount;
            }

            function placeBet(betType) {
                alert('下注成功 (' + currentChip + ' USDT): ' + betType);
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
