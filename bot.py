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
    
    webapp_url = os.getenv("RENDER_EXTERNAL_URL", "https://your-app-name.onrender.com")
    keyboard = [[InlineKeyboardButton("🎰 VÀO BÀN BACCARAT (LIVE)", web_app=WebAppInfo(url=webapp_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

# FastAPI phục vụ trực tiếp giao diện HTML bên trong code
web_app = FastAPI()

@web_app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Baccarat Live Casino</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
            body { background-color: #0b1016; color: #fff; overflow-x: hidden; display: flex; flex-direction: column; height: 100vh; }
            .top-bar { display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.6); padding: 8px 12px; font-size: 13px; z-index: 10; border-bottom: 1px solid rgba(255,255,255,0.1); }
            .top-left, .top-right { display: flex; align-items: center; gap: 10px; }
            .btn-exit { background: none; border: none; color: #fff; font-size: 16px; cursor: pointer; display: flex; align-items: center; gap: 4px; }
            .balance-box { background: rgba(255,255,255,0.1); padding: 4px 10px; border-radius: 12px; display: flex; align-items: center; gap: 6px; cursor: pointer; }
            .balance-box span { color: #f1c40f; font-weight: bold; }
            .dealer-screen { position: relative; width: 100%; height: 220px; background: #1c232a; overflow: hidden; display: flex; flex-direction: column; align-items: center; }
            .dealer-screen img { width: 100%; height: 100%; object-fit: cover; opacity: 0.85; }
            .table-info-overlay { position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.5); padding: 6px 10px; border-radius: 6px; font-size: 11px; border-left: 3px solid #e74c3c; }
            .time-box { position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,0.5); padding: 6px 10px; border-radius: 6px; font-size: 11px; text-align: right; }
            .cards-dealer-area { position: absolute; bottom: 15px; width: 100%; display: flex; justify-content: space-around; padding: 0 20px; z-index: 5; }
            .card-group { display: flex; flex-direction: column; align-items: center; background: rgba(0,0,0,0.4); padding: 5px 10px; border-radius: 8px; }
            .card-group-title { font-size: 11px; margin-bottom: 3px; color: #ccc; }
            .card-slots { display: flex; gap: 4px; min-height: 45px; align-items: center; }
            .playing-card { width: 32px; height: 45px; background: #fff; color: #000; border-radius: 4px; font-weight: bold; font-size: 12px; display: flex; justify-content: center; align-items: center; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
            .playing-card.red { color: #e74c3c; }
            .playing-card.hidden { background: #2980b9; color: transparent; border: 1px solid #fff; }
            .game-panel { flex: 1; display: flex; flex-direction: column; background: #141c24; padding: 8px; justify-content: space-between; }
            .round-info-bar { display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #aaa; padding: 0 5px; }
            .timer-circle { width: 30px; height: 30px; border-radius: 50%; background: #e74c3c; display: flex; justify-content: center; align-items: center; font-weight: bold; font-size: 14px; color: #fff; }
            .bet-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px; margin: 5px 0; }
            .bet-spot { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 8px 4px; text-align: center; cursor: pointer; position: relative; }
            .bet-spot.player { border-color: #3498db; }
            .bet-spot.banker { border-color: #e74c3c; }
            .bet-spot.tie { border-color: #2ecc71; }
            .bet-title { font-size: 13px; font-weight: bold; }
            .bet-rate { font-size: 10px; color: #f1c40f; }
            .bet-spot.player .bet-title { color: #3498db; }
            .bet-spot.banker .bet-title { color: #e74c3c; }
            .bet-spot.tie .bet-title { color: #2ecc71; }
            .my-bet-amount { position: absolute; bottom: 2px; right: 4px; font-size: 10px; background: #f1c40f; color: #000; padding: 1px 4px; border-radius: 4px; font-weight: bold; display: none; }
            .action-row { display: flex; justify-content: space-between; gap: 10px; margin-bottom: 5px; }
            .action-btn { flex: 1; background: rgba(255,255,255,0.1); border: none; padding: 6px; border-radius: 4px; color: #fff; font-size: 12px; cursor: pointer; display: flex; justify-content: center; align-items: center; gap: 4px; }
            .chips-bar { display: flex; justify-content: space-around; align-items: center; padding: 5px 0; background: rgba(0,0,0,0.3); border-radius: 8px; }
            .chip { width: 38px; height: 38px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-weight: bold; font-size: 11px; cursor: pointer; border: 2px dashed #fff; }
            .chip.selected { transform: scale(1.15); border-style: solid; border-color: #f1c40f; }
            .scoreboard-container { background: #0b1016; border-top: 1px solid rgba(255,255,255,0.1); padding: 6px; }
            .scoreboard-header { display: flex; justify-content: space-between; font-size: 11px; color: #888; margin-bottom: 4px; }
            .bead-plate { display: flex; gap: 3px; overflow-x: auto; padding-bottom: 4px; }
            .bead-item { width: 18px; height: 18px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 9px; font-weight: bold; flex-shrink: 0; }
            .bead-P { background: #3498db; color: #fff; }
            .bead-B { background: #e74c3c; color: #fff; }
            .bead-T { background: #2ecc71; color: #fff; }
        </style>
    </head>
    <body>
        <div class="top-bar">
            <div class="top-left">
                <button class="btn-exit" onclick="alert('Thoát bàn thành công!')">← <span>返回</span></button>
                <div class="balance-box"><span>🪙</span> <span id="user-balance">1,705.00</span></div>
            </div>
        </div>
        <div class="dealer-screen">
            <img src="https://images.unsplash.com/photo-1511193311914-0346f16efe90?auto=format&fit=crop&w=600&q=80" alt="Dealer">
            <div class="table-info-overlay"><div>B10 BACCARAT</div></div>
            <div class="time-box"><div id="live-time">15:48</div></div>
            <div class="cards-dealer-area">
                <div class="card-group">
                    <div class="card-group-title">PLAYER (闲)</div>
                    <div class="card-slots" id="player-cards"><div class="playing-card hidden">?</div><div class="playing-card hidden">?</div></div>
                </div>
                <div class="card-group">
                    <div class="card-group-title">BANKER (庄)</div>
                    <div class="card-slots" id="banker-cards"><div class="playing-card hidden">?</div><div class="playing-card hidden">?</div></div>
                </div>
            </div>
        </div>
        <div class="game-panel">
            <div class="round-info-bar">
                <span>Trạng thái: <strong id="game-status" style="color:#2ecc71;">Đang đặt cược</strong></span>
                <div class="timer-circle" id="timer">15</div>
            </div>
            <div class="bet-grid">
                <div class="bet-spot player" onclick="placeBet('player')"><div class="bet-title">闲 PLAYER</div><div class="bet-rate">1 : 1</div><div class="my-bet-amount" id="bet-player-amt">0</div></div>
                <div class="bet-spot tie" onclick="placeBet('tie')"><div class="bet-title">和 TIE</div><div class="bet-rate">1 : 8</div><div class="my-bet-amount" id="bet-tie-amt">0</div></div>
                <div class="bet-spot banker" onclick="placeBet('banker')"><div class="bet-title">庄 BANKER</div><div class="bet-rate">1 : 1</div><div class="my-bet-amount" id="bet-banker-amt">0</div></div>
            </div>
            <div class="action-row">
                <button class="action-btn" onclick="cancelBets()">✕ Hủy cược</button>
                <button class="action-btn" onclick="doubleBets()">⇋ Nhân đôi</button>
            </div>
            <div class="chips-bar">
                <div class="chip selected" onclick="selectChip(10, this)">10</div>
                <div class="chip" onclick="selectChip(50, this)">50</div>
                <div class="chip" onclick="selectChip(100, this)">100</div>
                <div class="chip" onclick="selectChip(500, this)">500</div>
            </div>
        </div>
        <div class="scoreboard-container">
            <div class="scoreboard-header"><span>Soi cầu</span></div>
            <div class="bead-plate" id="bead-plate"><div class="bead-item bead-P">P</div><div class="bead-item bead-B">B</div></div>
        </div>
        <script>
            let balance = 1705.00, selectedChipVal = 10, currentBets = { player: 0, banker: 0, tie: 0 };
            function selectChip(val, el) {
                document.querySelectorAll('.chip').forEach(c => c.classList.remove('selected'));
                el.classList.add('selected');
                selectedChipVal = val;
            }
            function placeBet(type) {
                if (balance < selectedChipVal) { alert('Số dư không đủ!'); return; }
                balance -= selectedChipVal; currentBets[type] += selectedChipVal;
                document.getElementById('user-balance').innerText = balance.toFixed(2);
                let amtEl = document.getElementById(`bet-${type}-amt`);
                amtEl.style.display = 'block'; amtEl.innerText = currentBets[type];
            }
            function cancelBets() {
                balance += currentBets.player + currentBets.banker + currentBets.tie;
                currentBets = { player: 0, banker: 0, tie: 0 };
                document.getElementById('user-balance').innerText = balance.toFixed(2);
                ['player', 'banker', 'tie'].forEach(t => document.getElementById(`bet-${t}-amt`).style.display = 'none');
            }
            function doubleBets() {
                let req = currentBets.player + currentBets.banker + currentBets.tie;
                if (balance < req) { alert('Không đủ số dư!'); return; }
                balance -= req; currentBets.player *= 2; currentBets.banker *= 2; currentBets.tie *= 2;
                document.getElementById('user-balance').innerText = balance.toFixed(2);
                if(currentBets.player > 0) document.getElementById('bet-player-amt').innerText = currentBets.player;
                if(currentBets.banker > 0) document.getElementById('bet-banker-amt').innerText = currentBets.banker;
                if(currentBets.tie > 0) document.getElementById('bet-tie-amt').innerText = currentBets.tie;
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
        print("❌ Lỗi: Chưa cấu hình BOT_TOKEN!")
    else:
        web_thread = threading.Thread(target=run_web, daemon=True)
        web_thread.start()

        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start_command))
        
        print("🤖 Bot Telegram tích hợp Baccarat Mini App đã khởi chạy thành công...")
        app.run_polling()
