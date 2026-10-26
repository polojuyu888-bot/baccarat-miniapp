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

# FastAPI: Giao diện Mini App Baccarat chuẩn chỉnh đồ họa 3D nhân vật ảo
web_app = FastAPI()

@web_app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Live Baccarat VIP</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            * { box-sizing: border-box; }
            body { background-color: #520813; color: #fff; font-family: Arial, "Helvetica Neue", sans-serif; margin: 0; padding: 0; user-select: none; }
            
            /* Khung Dealer 3D phía trên */
            .dealer-3d-container { 
                position: relative; 
                width: 100%; 
                height: 180px; 
                background: url('https://images.unsplash.com/photo-1511193311914-0346f16efe90?auto=format&fit=crop&w=800&q=80') center/cover no-repeat; 
                border-bottom: 2px solid #d4af37; 
                display: flex; 
                flex-direction: column; 
                justify-content: flex-end; 
                align-items: center; 
            }
            .dealer-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(82,8,19,0.95) 100%); }
            
            /* Nhân vật hoạt họa 3D (Ảnh đồ họa phong cách 3D game) */
            .dealer-3d-character { 
                position: absolute; 
                top: 8px; 
                left: 50%; 
                transform: translateX(-50%); 
                width: 80px; 
                height: 80px; 
                border-radius: 50%; 
                border: 2px solid #ffd700; 
                background: url('https://api.dicebear.com/7.x/bottts/svg?seed=Baccarat3DDealerAI') #1e293b center/cover no-repeat; 
                box-shadow: 0 0 15px rgba(255, 215, 0, 0.8); 
                z-index: 5; 
            }
            
            .live-badge { position: absolute; top: 6px; left: 6px; background: rgba(220, 38, 38, 0.9); color: white; padding: 2px 6px; font-size: 10px; font-weight: bold; border-radius: 4px; display: flex; align-items: center; gap: 4px; z-index: 10; }
            .live-badge::before { content: ''; width: 5px; height: 5px; background: #fff; border-radius: 50%; animation: blink 1s infinite; }
            @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.2; } 100% { opacity: 1; } }

            .dealer-table-3d { position: relative; z-index: 3; display: flex; width: 92%; justify-content: space-around; align-items: center; margin-bottom: 6px; }
            .cards-box { background: rgba(15, 23, 42, 0.85); border: 1px solid #d4af37; border-radius: 6px; padding: 4px; width: 44%; text-align: center; }
            .p-title { font-weight: bold; font-size: 10px; margin-bottom: 2px; }
            .cards-flex { display: flex; justify-content: center; gap: 3px; }
            .card { width: 24px; height: 34px; background: #fff; color: #000; border-radius: 2px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 11px; }
            .card.red { color: #dc2626; }
            .score-badge { display: inline-block; background: #d4af37; color: #000; font-size: 9px; font-weight: bold; padding: 1px 4px; border-radius: 6px; margin-top: 2px; }

            /* Dòng thông tin trên cùng */
            .top-bar { display: flex; justify-content: space-between; align-items: center; padding: 6px 12px; font-size: 11px; color: #f3a9b3; background: rgba(0,0,0,0.3); }
            .timer-circle { width: 26px; height: 26px; border-radius: 50%; border: 2px solid #facc15; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #fff; font-size: 12px; background: rgba(0,0,0,0.5); }
            
            /* Khung cược chính */
            .table-board { background: #680d1b; border: 1px solid #8e1828; margin: 4px; border-radius: 12px; padding: 6px; box-shadow: inset 0 0 10px rgba(0,0,0,0.5); position: relative; }
            
            /* Cửa cược phụ (5 ô) */
            .side-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 4px; margin-bottom: 6px; }
            .side-box { background: rgba(0, 0, 0, 0.25); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; padding: 6px 2px; text-align: center; position: relative; cursor: pointer; min-height: 65px; display: flex; flex-direction: column; justify-content: center; }
            .side-box:active { background: rgba(255, 255, 255, 0.15); }
            .sb-name { font-size: 11px; font-weight: bold; }
            .sb-name.cyan { color: #38bdf8; }
            .sb-name.gold { color: #fde047; }
            .sb-name.orange { color: #fb923c; }
            .help-icon { position: absolute; top: 2px; right: 2px; font-size: 9px; width: 11px; height: 11px; border-radius: 50%; background: rgba(255,255,255,0.2); display: flex; align-items: center; justify-content: center; color: #ccc; }
            .sb-odds { font-size: 10px; margin: 2px 0; color: #fff; font-weight: bold; }
            .sb-sub { font-size: 8px; color: #fca5a5; scale: 0.9; }
            .sb-status { font-size: 8px; color: #9aa0a6; margin-top: 2px; }

            /* Cửa cược chính (3 ô lớn) */
            .main-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px; }
            .main-box { background: rgba(0, 0, 0, 0.25); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; padding: 10px 4px; text-align: center; position: relative; cursor: pointer; min-height: 85px; display: flex; flex-direction: column; justify-content: center; align-items: center; }
            .main-box:active { background: rgba(255, 255, 255, 0.15); }
            .mb-name { font-size: 20px; font-weight: bold; }
            .mb-name.player { color: #38bdf8; }
            .mb-name.tie { color: #4ade80; }
            .mb-name.banker { color: #f87171; }
            .mb-odds { font-size: 12px; font-weight: bold; color: #fff; margin: 2px 0; }
            .mb-stats { font-size: 9px; color: #9aa0a6; display: flex; align-items: center; gap: 3px; }
            .percent-badge { position: absolute; top: 6px; right: 6px; font-size: 9px; padding: 1px 4px; border-radius: 8px; background: rgba(0,0,0,0.4); color: #cbd5e1; }

            /* Chip cược chồng lên ô */
            .chip-stack { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); display: flex; flex-direction: column; align-items: center; z-index: 10; pointer-events: none; }
            .chip-amount { background: rgba(0,0,0,0.85); color: #fff; font-size: 9px; font-weight: bold; padding: 1px 5px; border-radius: 8px; border: 1px solid #ffd700; margin-bottom: 2px; }
            .chip-icon { width: 28px; height: 28px; border-radius: 50%; background: radial-gradient(circle, #a855f7 0%, #6b21a8 100%); border: 2px dashed #fff; display: flex; align-items: center; justify-content: center; font-size: 8px; font-weight: bold; color: white; box-shadow: 0 3px 6px rgba(0,0,0,0.6); }

            /* Nút Hủy & X2 */
            .bottom-actions { display: flex; justify-content: space-between; align-items: center; padding: 10px 20px; margin-top: 4px; }
            .action-btn { background: transparent; border: none; color: #e2e8f0; font-size: 14px; font-weight: bold; display: flex; align-items: center; gap: 6px; cursor: pointer; opacity: 0.9; }
            .action-btn:active { opacity: 0.6; transform: scale(0.96); }

            /* Thanh chọn Chip phía dưới */
            .chip-bar { background: #3b060d; padding: 8px 12px; display: flex; justify-content: space-around; align-items: center; border-top: 1px solid #680d1b; position: sticky; bottom: 0; }
            .chip-item { width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 11px; cursor: pointer; border: 2px dashed #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
            .chip-item.active { border-style: solid; border-color: #ffd700; transform: scale(1.15); box-shadow: 0 0 10px #ffd700; }
            .c-10 { background: #22c55e; color: #fff; }
            .c-50 { background: #3b82f6; color: #fff; }
            .c-100 { background: #a855f7; color: #fff; }
            .c-500 { background: #ef4444; color: #fff; }
            .c-1000 { background: #eab308; color: #000; }
        </style>
    </head>
    <body>

        <!-- 1. Màn hình Dealer Hoạt họa 3D chuẩn xác -->
        <div class="dealer-3d-container">
            <div class="dealer-overlay"></div>
            <div class="live-badge">3D LIVE VIP</div>
            <div class="dealer-3d-character"></div>

            <div class="dealer-table-3d">
                <div class="cards-box">
                    <div class="p-title" style="color: #60a5fa;">闲 (PLAYER)</div>
                    <div class="cards-flex">
                        <div class="card red">A ♥</div>
                        <div class="card">A ♣</div>
                    </div>
                    <div class="score-badge">2 点</div>
                </div>
                <div class="cards-box">
                    <div class="p-title" style="color: #f87171;">庄 (BANKER)</div>
                    <div class="cards-flex">
                        <div class="card red">9 ♦</div>
                        <div class="card">10 ♠</div>
                    </div>
                    <div class="score-badge">9 点</div>
                </div>
            </div>
        </div>

        <!-- 2. Dòng thông tin trên cùng (UTC+8, Thời gian thực, Giới hạn cược) -->
        <div class="top-bar">
            <span id="beijing-time">22:07 (UTC+08)</span>
            <div class="timer-circle" id="countdown">12</div>
            <span>限红: 10~20,000</span>
        </div>

        <div style="padding: 0 6px; font-size: 10px; color: #cbd5e1; margin-bottom: 2px;">
            局号: <span id="table-id">GBE4AB3EC4C1</span>
        </div>

        <!-- 3. Khung bàn đặt cược -->
        <div class="table-board">
            
            <!-- Cửa cược phụ (5 ô) -->
            <div class="side-grid">
                <div class="side-box" onclick="placeBet('player_pair')">
                    <span class="help-icon">?</span>
                    <div class="sb-name cyan">闲对</div>
                    <div class="sb-odds">1:11</div>
                    <div class="sb-status">6局未出</div>
                    <div id="chip-player_pair"></div>
                </div>
                <div class="side-box" onclick="placeBet('lucky_7')">
                    <span class="help-icon">?</span>
                    <div class="sb-name cyan">幸运七</div>
                    <div class="sb-sub">闲7点赢<br>2张牌 1:6<br>3张牌 1:15</div>
                    <div class="sb-status">8局未出</div>
                    <div id="chip-lucky_7"></div>
                </div>
                <div class="side-box" onclick="placeBet('super_lucky_7')">
                    <span class="help-icon">?</span>
                    <div class="sb-name gold">超级幸运七</div>
                    <div class="sb-sub">闲7赢庄6<br>4张牌 1:30/5张牌 1:40<br>6张牌 1:100</div>
                    <div class="sb-status">18局未出</div>
                    <div id="chip-super_lucky_7"></div>
                </div>
                <div class="side-box" onclick="placeBet('lucky_6')">
                    <span class="help-icon">?</span>
                    <div class="sb-name orange">幸运六</div>
                    <div class="sb-sub">庄6点赢<br>2张牌 1:12<br>3张牌 1:20</div>
                    <div class="sb-status">22局未出</div>
                    <div id="chip-lucky_6"></div>
                </div>
                <div class="side-box" onclick="placeBet('banker_pair')">
                    <span class="help-icon">?</span>
                    <div class="sb-name orange">庄对</div>
                    <div class="sb-odds">1:11</div>
                    <div class="sb-status">11局未出</div>
                    <div id="chip-banker_pair"></div>
                </div>
            </div>

            <!-- Cửa cược chính (3 ô lớn) -->
            <div class="main-grid">
                <div class="main-box" onclick="placeBet('player')">
                    <span class="percent-badge">36%</span>
                    <div class="mb-name player">闲</div>
                    <div class="mb-odds">1:1</div>
                    <div class="mb-stats">👥 14 🪙 1K</div>
                    <div id="chip-player"></div>
                </div>
                <div class="main-box" onclick="placeBet('tie')">
                    <span class="percent-badge">0%</span>
                    <div class="mb-name tie">和</div>
                    <div class="mb-odds">1:8</div>
                    <div class="mb-stats">7局未出</div>
                    <div id="chip-tie"></div>
                </div>
                <div class="main-box" onclick="placeBet('banker')">
                    <span class="percent-badge">64%</span>
                    <div class="mb-name banker">庄</div>
                    <div class="mb-odds">1:1</div>
                    <div class="mb-stats">👥 7 🪙 1.8K</div>
                    <div id="chip-banker"></div>
                </div>
            </div>

            <!-- Nút Hủy & X2 -->
            <div class="bottom-actions">
                <button class="action-btn" onclick="cancelBets()">
                    <span style="font-size: 15px;">✕</span> 取消
                </button>
                <button class="action-btn" onclick="doubleBets()">
                    <span style="font-size: 15px;">︽</span> X2
                </button>
            </div>
        </div>

        <!-- 4. Thanh chọn Chip phía dưới -->
        <div class="chip-bar">
            <div class="chip-item c-10 active" onclick="selectChip(10, this)">10</div>
            <div class="chip-item c-50" onclick="selectChip(50, this)">50</div>
            <div class="chip-item c-100" onclick="selectChip(100, this)">100</div>
            <div class="chip-item c-500" onclick="selectChip(500, this)">500</div>
            <div class="chip-item c-1000" onclick="selectChip(1000, this)">1k</div>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();

            let currentChip = 10;
            let bets = {};

            // Giờ Bắc Kinh UTC+8
            function updateBeijingTime() {
                let now = new Date();
                let utc = now.getTime() + (now.getTimezoneOffset() * 60000);
                let bjTime = new Date(utc + (3600000 * 8));
                let h = String(bjTime.getHours()).padStart(2, '0');
                let m = String(bjTime.getMinutes()).padStart(2, '0');
                document.getElementById('beijing-time').innerText = h + ':' + m + ' (UTC+08)';
            }
            setInterval(updateBeijingTime, 1000);
            updateBeijingTime();

            // Mã bàn ngẫu nhiên không trùng lặp
            function generateTableID() {
                let chars = '0123456789ABCDEF';
                let res = 'GB';
                for (let i = 0; i < 10; i++) {
                    res += chars.charAt(Math.floor(Math.random() * chars.length));
                }
                document.getElementById('table-id').innerText = res;
            }
            generateTableID();

            // Đếm ngược
            let timerVal = 12;
            setInterval(() => {
                timerVal--;
                if (timerVal < 0) timerVal = 12;
                document.getElementById('countdown').innerText = timerVal;
            }, 1000);

            function selectChip(amount, el) {
                document.querySelectorAll('.chip-item').forEach(c => c.classList.remove('active'));
                el.classList.add('active');
                currentChip = amount;
            }

            function placeBet(area) {
                if (!bets[area]) bets[area] = 0;
                bets[area] += currentChip;
                renderChips();
            }

            function renderChips() {
                let areas = ['player_pair', 'lucky_7', 'super_lucky_7', 'lucky_6', 'banker_pair', 'player', 'tie', 'banker'];
                areas.forEach(area => {
                    let container = document.getElementById('chip-' + area);
                    if (container) {
                        if (bets[area] && bets[area] > 0) {
                            container.innerHTML = `
                                <div class="chip-stack">
                                    <div class="chip-amount">${bets[area]}</div>
                                    <div class="chip-icon">Chip</div>
                                </div>
                            `;
                        } else {
                            container.innerHTML = '';
                        }
                    }
                });
            }

            function cancelBets() {
                bets = {};
                renderChips();
            }

            function doubleBets() {
                Object.keys(bets).forEach(area => {
                    if (bets[area] > 0) {
                        bets[area] *= 2;
                    }
                });
                renderChips();
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
