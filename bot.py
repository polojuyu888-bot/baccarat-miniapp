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

    display_balance = "∞ (Vô tận)" if is_admin(user_id) else f"{balance} ¥"

    welcome_text = (
        "🤖 **CHÀO MỪNG ĐẾN VỚI SÒNG BÀI BACCARAT VIP** 🤖\n\n"
        "✨ Hệ thống bàn cược trực tuyến chuẩn quốc tế.\n"
        f"🆔 **ID của bạn:** `{casino_id}`\n"
        f"💰 **Số dư ví:** `{display_balance}`\n\n"
        "👇 Nhấn nút bên dưới để mở bàn chơi giao diện trực tiếp:"
    )
    
    webapp_url = os.getenv("RENDER_EXTERNAL_URL", "https://your-app-name.onrender.com")
    keyboard = [[InlineKeyboardButton("🎰 VÀO BÀN BACCARAT (LIVE VIP)", web_app=WebAppInfo(url=webapp_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

# FastAPI phục vụ trực tiếp giao diện HTML mới nhất
web_app = FastAPI()

@web_app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Live Baccarat VIP</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
            body { background-color: #0b1016; color: #fff; overflow-x: hidden; display: flex; flex-direction: column; height: 100vh; user-select: none; }
            
            .top-bar { display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.7); padding: 8px 12px; font-size: 13px; z-index: 10; border-bottom: 1px solid rgba(255,255,255,0.1); }
            .top-left, .top-right { display: flex; align-items: center; gap: 8px; }
            .btn-exit { background: none; border: none; color: #fff; font-size: 15px; cursor: pointer; display: flex; align-items: center; gap: 4px; }
            .balance-box { background: rgba(255,255,255,0.12); padding: 4px 10px; border-radius: 12px; display: flex; align-items: center; gap: 6px; cursor: pointer; }
            .balance-box span { color: #f1c40f; font-weight: bold; }
            
            .dealer-screen { position: relative; width: 100%; height: 210px; background: #1c232a; overflow: hidden; display: flex; flex-direction: column; align-items: center; border-bottom: 2px solid #d4af37; }
            .dealer-screen img { width: 100%; height: 100%; object-fit: cover; opacity: 0.9; }
            
            .table-info-overlay { position: absolute; top: 8px; left: 8px; background: rgba(0,0,0,0.6); padding: 4px 8px; border-radius: 4px; font-size: 10px; border-left: 3px solid #e74c3c; }
            .time-box { position: absolute; top: 8px; right: 8px; background: rgba(0,0,0,0.6); padding: 4px 8px; border-radius: 4px; font-size: 10px; text-align: right; }

            .game-panel { flex: 1; display: flex; flex-direction: column; background: #680d1b; padding: 6px; justify-content: space-between; }
            .round-info-bar { display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #f3a9b3; padding: 0 4px; }
            
            .side-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 3px; margin: 4px 0; }
            .side-spot { background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 4px 2px; text-align: center; cursor: pointer; position: relative; min-height: 58px; display: flex; flex-direction: column; justify-content: center; align-items: center; }
            .side-spot:active { background: rgba(255,255,255,0.2); }
            .s-title { font-size: 10px; font-weight: bold; }
            .s-title.cyan { color: #38bdf8; }
            .s-title.gold { color: #fde047; }
            .s-title.orange { color: #fb923c; }
            .s-rate { font-size: 9px; color: #fff; margin: 1px 0; }
            .s-sub { font-size: 7px; color: #fca5a5; line-height: 1; }
            .s-status { font-size: 7px; color: #9aa0a6; margin-top: 1px; }

            .main-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px; margin-bottom: 4px; }
            .main-spot { background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 8px 4px; text-align: center; cursor: pointer; position: relative; min-height: 75px; display: flex; flex-direction: column; justify-content: center; align-items: center; }
            .main-spot:active { background: rgba(255,255,255,0.2); }
            .m-name { font-size: 18px; font-weight: bold; }
            .m-name.player { color: #38bdf8; }
            .m-name.tie { color: #4ade80; }
            .m-name.banker { color: #f87171; }
            .m-rate { font-size: 11px; font-weight: bold; color: #fff; }
            .m-stats { font-size: 8px; color: #cbd5e1; margin-top: 2px; }
            
            .my-bet-tag { position: absolute; bottom: 2px; right: 4px; font-size: 9px; background: #f1c40f; color: #000; padding: 1px 4px; border-radius: 4px; font-weight: bold; display: none; z-index: 5; }

            .action-row { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 4px; }
            .action-btn { flex: 1; background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.2); padding: 5px; border-radius: 4px; color: #fff; font-size: 11px; font-weight: bold; cursor: pointer; display: flex; justify-content: center; align-items: center; gap: 4px; }
            .action-btn:active { background: rgba(255,255,255,0.3); }

            .chips-container { display: flex; align-items: center; background: rgba(0,0,0,0.5); padding: 6px 8px; border-radius: 8px; justify-content: space-between; gap: 4px; }
            .menu-chip-btn { width: 32px; height: 32px; border-radius: 50%; background: #334155; border: 1px solid #64748b; display: flex; justify-content: center; align-items: center; cursor: pointer; font-size: 12px; }
            
            .chips-scroll { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; align-items: center; padding: 2px; }
            .chips-scroll::-webkit-scrollbar { display: none; }
            
            .chip { width: 36px; height: 36px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-weight: bold; font-size: 10px; cursor: pointer; border: 2px dashed #fff; flex-shrink: 0; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
            .chip.selected { transform: scale(1.15); border-style: solid; border-color: #f1c40f; box-shadow: 0 0 8px #f1c40f; }
            .c-5 { background: #3b82f6; color: #fff; }
            .c-10 { background: #eab308; color: #000; }
            .c-500 { background: #a855f7; color: #fff; }
            .c-2000 { background: #ef4444; color: #fff; }
            .c-5k { background: #10b981; color: #fff; }
            .c-10k { background: #f97316; color: #fff; }
            .c-20k { background: #6366f1; color: #fff; }

            .commission-toggle { display: flex; align-items: center; gap: 3px; font-size: 9px; cursor: pointer; }
            .toggle-switch { width: 28px; height: 15px; background: #cbd5e1; border-radius: 10px; position: relative; transition: 0.3s; }
            .toggle-switch::before { content: ''; position: absolute; width: 11px; height: 11px; background: #fff; border-radius: 50%; top: 2px; left: 2px; transition: 0.3s; }
            input.comm-input { display: none; }
            input.comm-input:checked + .toggle-switch { background: #22c55e; }
            input.comm-input:checked + .toggle-switch::before { transform: translateX(13px); }

            .scoreboard-section { background: #141c24; border-top: 1px solid rgba(255,255,255,0.15); padding: 6px; }
            .sc-top { display: flex; justify-content: space-between; align-items: center; font-size: 10px; color: #94a3b8; margin-bottom: 4px; }
            .sc-indicators { display: flex; gap: 8px; font-size: 9px; }
            
            .bead-plate-grid { display: grid; grid-template-rows: repeat(6, 1fr); grid-auto-flow: column; gap: 3px; overflow-x: auto; padding-bottom: 4px; max-height: 110px; }
            .bead { width: 15px; height: 15px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 8px; font-weight: bold; flex-shrink: 0; }
            .bead.P { background: #3b82f6; color: #fff; }
            .bead.B { background: #ef4444; color: #fff; }
            .bead.T { background: #10b981; color: #fff; }

            .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 100; justify-content: center; align-items: center; }
            .modal-content { background: #1c232a; width: 90%; max-height: 80vh; border-radius: 8px; padding: 15px; overflow-y: auto; }
            .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px; font-size: 14px; }
            .close-modal { background: none; border: none; color: #fff; font-size: 18px; cursor: pointer; }
            .history-list { font-size: 11px; display: flex; flex-direction: column; gap: 6px; }
            .history-item { background: rgba(255,255,255,0.05); padding: 8px; border-radius: 4px; display: flex; justify-content: space-between; }
        </style>
    </head>
    <body>
        <div class="top-bar">
            <div class="top-left">
                <button class="btn-exit" onclick="alert('Đã thoát bàn thành công!')">← <span>返回</span></button>
                <div class="balance-box" onclick="openHistoryModal()">
                    <span>¥</span> <span id="user-balance">1,705.00</span>
                </div>
            </div>
            <div class="top-right">
                <span style="font-size:11px; color:#cbd5e1;">📶 🔊 ⚙️ 🔲</span>
            </div>
        </div>

        <div class="dealer-screen">
            <img src="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=800&q=80" alt="Dealer Live">
            <div class="table-info-overlay">
                <div id="table-name" style="font-weight: bold;">B10 BACCARAT</div>
                <div style="font-size: 8px; color: #aaa;" id="table-id-code">GB10269234DA</div>
            </div>
            <div class="time-box">
                <div id="hanoi-time" style="font-weight: bold;">15:48 (UTC+07)</div>
                <div style="font-size: 8px; color: #aaa;">限红: 10~20,000</div>
            </div>
        </div>

        <div class="game-panel">
            <div class="round-info-bar">
                <span>Trạng thái: <strong id="game-status" style="color:#2ecc71;">Đang đặt cược</strong></span>
                <span style="background: rgba(0,0,0,0.4); padding: 2px 6px; border-radius: 10px; color: #facc15;" id="timer-val">⏳ 12s</span>
                <span>Tối đa: 20,000</span>
            </div>

            <div class="side-grid">
                <div class="side-spot" onclick="placeBet('player_pair')">
                    <div class="s-title cyan">闲对</div>
                    <div class="s-rate">1:11</div>
                    <div class="s-status">6局未出</div>
                    <div class="my-bet-tag" id="amt-player_pair">0</div>
                </div>
                <div class="side-spot" onclick="placeBet('lucky_7')">
                    <div class="s-title cyan">幸运七</div>
                    <div class="s-sub">闲7点赢<br>2张 1:6<br>3张 1:15</div>
                    <div class="s-status">8局未出</div>
                    <div class="my-bet-tag" id="amt-lucky_7">0</div>
                </div>
                <div class="side-spot" onclick="placeBet('super_lucky_7')">
                    <div class="s-title gold">超级幸运七</div>
                    <div class="s-sub">闲7赢庄6<br>4张 1:30<br>6张 1:100</div>
                    <div class="s-status">18局未出</div>
                    <div class="my-bet-tag" id="amt-super_lucky_7">0</div>
                </div>
                <div class="side-spot" onclick="placeBet('lucky_6')">
                    <div class="s-title orange">幸运六</div>
                    <div class="s-sub">庄6点赢<br>2张 1:12<br>3张 1:20</div>
                    <div class="s-status">22局未出</div>
                    <div class="my-bet-tag" id="amt-lucky_6">0</div>
                </div>
                <div class="side-spot" onclick="placeBet('banker_pair')">
                    <div class="s-title orange">庄对</div>
                    <div class="s-rate">1:11</div>
                    <div class="s-status">11局未出</div>
                    <div class="my-bet-tag" id="amt-banker_pair">0</div>
                </div>
            </div>

            <div class="main-grid">
                <div class="main-spot" onclick="placeBet('player')">
                    <span style="position: absolute; top: 4px; right: 6px; font-size: 8px; color: #94a3b8;">36%</span>
                    <div class="m-name player">闲</div>
                    <div class="m-rate" id="rate-player">1 : 1</div>
                    <div class="m-stats">👥 14 🪙 1K</div>
                    <div class="my-bet-tag" id="amt-player">0</div>
                </div>
                <div class="main-spot" onclick="placeBet('tie')">
                    <span style="position: absolute; top: 4px; right: 6px; font-size: 8px; color: #94a3b8;">0%</span>
                    <div class="m-name tie">和</div>
                    <div class="m-rate">1 : 8</div>
                    <div class="m-stats">7局未出</div>
                    <div class="my-bet-tag" id="amt-tie">0</div>
                </div>
                <div class="main-spot" onclick="placeBet('banker')">
                    <span style="position: absolute; top: 4px; right: 6px; font-size: 8px; color: #94a3b8;">64%</span>
                    <div class="m-name banker">庄</div>
                    <div class="m-rate" id="rate-banker">1 : 0.95</div>
                    <div class="m-stats">👥 7 🪙 1.8K</div>
                    <div class="my-bet-tag" id="amt-banker">0</div>
                </div>
            </div>

            <div class="action-row">
                <button class="action-btn" onclick="cancelBets()">✕ 取消 (Hủy)</button>
                <button class="action-btn" onclick="doubleBets()">⇋ X2 (Nhân đôi)</button>
            </div>

            <div class="chips-container">
                <div class="menu-chip-btn" onclick="alert('Định mức chip hệ thống')">🎮</div>
                <div class="chips-scroll">
                    <div class="chip c-5" onclick="selectChip(5, this)">5</div>
                    <div class="chip c-10 selected" onclick="selectChip(10, this)">10</div>
                    <div class="chip c-500" onclick="selectChip(500, this)">500</div>
                    <div class="chip c-2000" onclick="selectChip(2000, this)">2K</div>
                    <div class="chip c-5k" onclick="selectChip(5000, this)">5K</div>
                    <div class="chip c-10k" onclick="selectChip(10000, this)">10K</div>
                    <div class="chip c-20k" onclick="selectChip(20000, this)">20K</div>
                </div>
                <div class="commission-toggle" onclick="toggleCommission()">
                    <span style="color: #cbd5e1;">免佣</span>
                    <input type="checkbox" id="comm-checkbox" class="comm-input">
                    <label for="comm-checkbox" class="toggle-switch" style="pointer-events: none;"></label>
                </div>
            </div>
        </div>

        <div class="scoreboard-section">
            <div class="sc-top">
                <div class="sc-indicators">
                    <span>庄问路</span>
                    <span>闲问路</span>
                    <span>好路投注</span>
                </div>
                <span>37 15 19 3 1 3 1</span>
            </div>
            <div class="bead-plate-grid" id="bead-plate-container"></div>
        </div>

        <div class="modal" id="history-modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Lịch sử đặt cược hôm nay</h3>
                    <button class="close-modal" onclick="closeHistoryModal()">✕</button>
                </div>
                <div class="history-list" id="history-list-content">
                    <div>Chưa có giao dịch đặt cược nào trong ngày hôm nay.</div>
                </div>
            </div>
        </div>

        <script>
            let balance = 1705.00;
            let selectedChip = 10;
            let isCommissionFree = false;
            let currentBets = { player: 0, banker: 0, tie: 0, player_pair: 0, banker_pair: 0, lucky_7: 0, super_lucky_7: 0, lucky_6: 0 };
            let todayHistory = [];

            function generateUniqueTable() {
                let randHex = Math.random().toString(16).substring(2, 10).toUpperCase();
                document.getElementById('table-id-code').innerText = 'GB' + randHex + 'DA';
                let tableNum = Math.floor(1 + Math.random() * 20);
                document.getElementById('table-name').innerText = `B${tableNum} BACCARAT`;
            }
            generateUniqueTable();

            setInterval(() => {
                let now = new Date();
                let utc = now.getTime() + (now.getTimezoneOffset() * 60000);
                let hanoiTime = new Date(utc + (3600000 * 7));
                let h = String(hanoiTime.getHours()).padStart(2, '0');
                let m = String(hanoiTime.getMinutes()).padStart(2, '0');
                let s = String(hanoiTime.getSeconds()).padStart(2, '0');
                document.getElementById('hanoi-time').innerText = `${h}:${m}:${s} (UTC+07)`;
            }, 1000);

            function selectChip(val, el) {
                document.querySelectorAll('.chip').forEach(c => c.classList.remove('selected'));
                el.classList.add('selected');
                selectedChip = val;
            }

            function toggleCommission() {
                let cb = document.getElementById('comm-checkbox');
                cb.checked = !cb.checked;
                isCommissionFree = cb.checked;
                document.getElementById('rate-banker').innerText = isCommissionFree ? '1 : 1' : '1 : 0.95';
            }

            function placeBet(type) {
                if (balance < selectedChip) {
                    alert('Số dư ví không đủ!');
                    return;
                }
                balance -= selectedChip;
                currentBets[type] += selectedChip;
                document.getElementById('user-balance').innerText = balance.toFixed(2);

                let tag = document.getElementById(`amt-${type}`);
                tag.style.display = 'block';
                tag.innerText = currentBets[type];

                todayHistory.push({
                    time: new Date().toLocaleTimeString(),
                    type: type,
                    amount: selectedChip
                });
            }

            function cancelBets() {
                let refund = Object.values(currentBets).reduce((a, b) => a + b, 0);
                balance += refund;
                currentBets = { player: 0, banker: 0, tie: 0, player_pair: 0, banker_pair: 0, lucky_7: 0, super_lucky_7: 0, lucky_6: 0 };
                document.getElementById('user-balance').innerText = balance.toFixed(2);
                ['player', 'banker', 'tie', 'player_pair', 'banker_pair', 'lucky_7', 'super_lucky_7', 'lucky_6'].forEach(t => {
                    document.getElementById(`amt-${t}`).style.display = 'none';
                });
            }

            function doubleBets() {
                let totalNeeded = Object.values(currentBets).reduce((a, b) => a + b, 0);
                if (balance < totalNeeded) {
                    alert('Không đủ số dư để nhân đôi!');
                    return;
                }
                balance -= totalNeeded;
                for (let key in currentBets) {
                    if (currentBets[key] > 0) {
                        currentBets[key] *= 2;
                        document.getElementById(`amt-${key}`).innerText = currentBets[key];
                    }
                }
                document.getElementById('user-balance').innerText = balance.toFixed(2);
            }

            function initScoreboard() {
                let container = document.getElementById('bead-plate-container');
                let sampleResults = ['P','B','P','P','B','T','B','P','B','B','P','P','P','B','T','B','P','B','P','B','B','P','T','P','B','P','B','P','B','B'];
                sampleResults.forEach(res => {
                    let div = document.createElement('div');
                    div.className = `bead ${res}`;
                    div.innerText = res;
                    container.appendChild(div);
                });
            }
            initScoreboard();

            function openHistoryModal() {
                document.getElementById('history-modal').style.display = 'flex';
                let listEl = document.getElementById('history-list-content');
                if (todayHistory.length === 0) {
                    listEl.innerHTML = `<div>Chưa có giao dịch đặt cược nào trong ngày hôm nay.</div>`;
                } else {
                    listEl.innerHTML = todayHistory.map(h => `
                        <div class="history-item">
                            <span>[${h.time}] Cửa: <strong>${h.type.toUpperCase()}</strong></span>
                            <span style="color: #f1c40f;">-${h.amount} ¥</span>
                        </div>
                    `).join('');
                }
            }
            function closeHistoryModal() {
                document.getElementById('history-modal').style.display = 'none';
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
