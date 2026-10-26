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
            balance REAL DEFAULT 0.0,
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
    conn.close()

    display_balance = "∞" if is_admin(user_id) else f"${balance:,.2f}"

    welcome_text = (
        "🤖 **SÒNG BÀI BACCARAT VIP CHUẨN QUỐC TẾ** 🤖\n\n"
        f"🆔 **ID tài khoản:** `{casino_id}`\n"
        f"💰 **Số dư hiện tại:** `{display_balance}`\n\n"
        "👇 Nhấn nút bên dưới để vào bàn chơi trực tiếp:"
    )
    
    webapp_url = os.getenv("RENDER_EXTERNAL_URL", "https://your-app-name.onrender.com")
    keyboard = [[InlineKeyboardButton("🎰 MỞ BÀN BACCARAT LIVE", web_app=WebAppInfo(url=webapp_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

web_app = FastAPI()

@web_app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Baccarat Live Casino VIP</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            body { background-color: #0b1016; color: #fff; overflow-x: hidden; display: flex; flex-direction: column; height: 100vh; user-select: none; }
            
            .top-bar { display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.75); padding: 8px 12px; font-size: 13px; z-index: 10; border-bottom: 1px solid rgba(255,255,255,0.1); }
            .top-left, .top-right { display: flex; align-items: center; gap: 8px; }
            .btn-exit { background: none; border: none; color: #fff; font-size: 15px; cursor: pointer; display: flex; align-items: center; gap: 4px; }
            .balance-box { background: rgba(255,255,255,0.12); padding: 4px 10px; border-radius: 12px; display: flex; align-items: center; gap: 6px; cursor: pointer; }
            .balance-box span { color: #f1c40f; font-weight: bold; }
            
            .dealer-screen { position: relative; width: 100%; height: 200px; background: #1c232a; overflow: hidden; display: flex; flex-direction: column; align-items: center; border-bottom: 2px solid #d4af37; }
            .dealer-screen img { width: 100%; height: 100%; object-fit: cover; opacity: 0.9; }
            
            .table-info-overlay { position: absolute; top: 8px; left: 8px; background: rgba(0,0,0,0.6); padding: 4px 8px; border-radius: 4px; font-size: 10px; border-left: 3px solid #e74c3c; }
            .time-box { position: absolute; top: 8px; right: 8px; background: rgba(0,0,0,0.6); padding: 4px 8px; border-radius: 4px; font-size: 10px; text-align: right; }

            .cards-on-table { position: absolute; bottom: 8px; width: 100%; display: flex; justify-content: space-around; padding: 0 15px; z-index: 5; pointer-events: none; }
            .table-side { display: flex; gap: 4px; align-items: center; background: rgba(0,0,0,0.4); padding: 4px 8px; border-radius: 6px; }
            
            .playing-card { width: 26px; height: 36px; perspective: 1000px; }
            .card-inner { width: 100%; height: 100%; position: relative; transform-style: preserve-3d; transition: transform 0.8s ease; }
            .playing-card.flipped .card-inner { transform: rotateY(180deg); }
            .card-face { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; border-radius: 4px; display: flex; justify-content: center; align-items: center; font-size: 10px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.5); }
            .card-back { background: #2563eb; color: transparent; border: 1px solid #fff; }
            .card-front { background: #fff; color: #000; transform: rotateY(180deg); }
            .card-front.red { color: #e74c3c; }

            .game-panel { flex: 1; display: flex; flex-direction: column; background: #680d1b; padding: 5px; justify-content: space-between; }
            .round-info-bar { display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #f3a9b3; padding: 0 4px; }
            
            .side-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 3px; margin: 2px 0; }
            .side-spot { background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 3px 2px; text-align: center; cursor: pointer; position: relative; min-height: 52px; display: flex; flex-direction: column; justify-content: center; align-items: center; }
            .s-title { font-size: 9px; font-weight: bold; }
            .s-title.cyan { color: #38bdf8; }
            .s-title.gold { color: #fde047; }
            .s-title.orange { color: #fb923c; }
            .s-rate { font-size: 8px; color: #fff; margin: 1px 0; }
            .s-sub { font-size: 6px; color: #fca5a5; line-height: 1; }
            .s-status { font-size: 6px; color: #9aa0a6; margin-top: 1px; }

            .main-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px; margin-bottom: 2px; }
            .main-spot { background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 6px 4px; text-align: center; cursor: pointer; position: relative; min-height: 65px; display: flex; flex-direction: column; justify-content: center; align-items: center; }
            .m-name { font-size: 16px; font-weight: bold; }
            .m-name.player { color: #38bdf8; }
            .m-name.tie { color: #4ade80; }
            .m-name.banker { color: #f87171; }
            .m-rate { font-size: 10px; font-weight: bold; color: #fff; }
            .m-stats { font-size: 8px; color: #cbd5e1; margin-top: 2px; }
            
            .my-bet-tag { position: absolute; bottom: 2px; right: 4px; font-size: 9px; background: #f1c40f; color: #000; padding: 1px 4px; border-radius: 4px; font-weight: bold; display: none; z-index: 5; }

            .action-row { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 2px; }
            .action-btn { flex: 1; background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.2); padding: 4px; border-radius: 4px; color: #fff; font-size: 10px; font-weight: bold; cursor: pointer; display: flex; justify-content: center; align-items: center; gap: 4px; }

            .chips-container { display: flex; align-items: center; background: rgba(0,0,0,0.5); padding: 4px 8px; border-radius: 8px; justify-content: space-between; gap: 4px; }
            .menu-chip-btn { width: 30px; height: 30px; border-radius: 50%; background: #334155; border: 1px solid #64748b; display: flex; justify-content: center; align-items: center; cursor: pointer; font-size: 11px; }
            
            .chips-scroll { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; align-items: center; padding: 2px; }
            .chips-scroll::-webkit-scrollbar { display: none; }
            
            .chip { width: 32px; height: 32px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-weight: bold; font-size: 10px; cursor: pointer; border: 2px dashed #fff; flex-shrink: 0; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
            .chip.selected { transform: scale(1.15); border-style: solid; border-color: #f1c40f; box-shadow: 0 0 8px #f1c40f; }
            .c-10 { background: #3b82f6; color: #fff; }
            .c-20 { background: #10b981; color: #fff; }
            .c-50 { background: #f97316; color: #fff; }
            .c-100 { background: #a855f7; color: #fff; }
            .c-200 { background: #ef4444; color: #fff; }
            .c-2k { background: #eab308; color: #000; }

            .commission-toggle { display: flex; align-items: center; gap: 3px; font-size: 9px; cursor: pointer; }
            .toggle-switch { width: 26px; height: 14px; background: #cbd5e1; border-radius: 10px; position: relative; transition: 0.3s; }
            .toggle-switch::before { content: ''; position: absolute; width: 10px; height: 10px; background: #fff; border-radius: 50%; top: 2px; left: 2px; transition: 0.3s; }
            input.comm-input { display: none; }
            input.comm-input:checked + .toggle-switch { background: #22c55e; }
            input.comm-input:checked + .toggle-switch::before { transform: translateX(12px); }

            /* BẢNG SOI CẦU: ĐÚNG 6 HÀNG DỌC, KHÔNG GẠCH NGANG, BIG ROAD BẮT ĐẦU TỪ CỘT 8 */
            .scoreboard-section { background: #141c24; border-top: 1px solid rgba(255,255,255,0.15); padding: 4px 6px; height: 120px; display: flex; flex-direction: column; justify-content: space-between; overflow: hidden; }
            .sc-header-row { display: flex; justify-content: space-between; align-items: center; width: 100%; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 2px; }
            
            .sc-stats-group { display: flex; align-items: center; gap: 10px; }
            .stat-item { display: flex; flex-direction: column; align-items: center; font-size: 10px; font-weight: bold; color: #ffffff !important; }
            .stat-item span { color: #ffffff !important; }

            .stat-icon-circle { width: 11px; height: 11px; border-radius: 50%; display: inline-block; margin-bottom: 1px; }
            .ratio-pie { width: 11px; height: 11px; border-radius: 50%; display: inline-block; margin-bottom: 1px; border: 1px solid rgba(255,255,255,0.3); background: #334155; }

            .sc-menus { display: flex; gap: 8px; align-items: center; }
            .sc-menu-item { display: flex; flex-direction: column; align-items: center; font-size: 8px; color: #94a3b8; cursor: pointer; background: rgba(255,255,255,0.05); padding: 1px 4px; border-radius: 3px; }
            .sc-menu-icons { display: flex; gap: 2px; align-items: center; margin-bottom: 1px; }

            .road-tables-container { 
                display: flex; 
                gap: 0px; 
                overflow: hidden; 
                align-items: flex-start; 
                height: 96px; 
                padding-top: 2px;
                background-image: radial-gradient(rgba(255, 255, 255, 0.18) 1px, transparent 1px);
                background-size: 15px 15px;
            }

            /* Bảng Bead Plate bên trái: Đúng 7 cột, đủ 6 hàng dọc (15px * 6 = 90px) */
            .bead-grid-table { display: grid; grid-template-rows: repeat(6, 15px); grid-auto-flow: column; grid-auto-columns: 15px; gap: 1px; height: 92px; align-content: start; }
            .bead-box { width: 15px; height: 15px; display: flex; justify-content: center; align-items: center; position: relative; }
            .bead { width: 13px; height: 13px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 6px; font-weight: bold; }
            .bead.P { background: #3b82f6; color: #fff; }
            .bead.B { background: #ef4444; color: #fff; }
            .bead.T { background: #10b981; color: #fff; }
            .bead.P7 { background: #3b82f6; color: #fff; border: 1px solid #facc15; font-size: 5px; }
            .bead.B6 { background: #ef4444; color: #fff; border: 1px solid #facc15; font-size: 5px; }

            /* Bảng Big Road bên phải: Cố định 16 cột (bắt đầu từ cột 8 đến 23), đủ 6 hàng dọc */
            .road-grid-table { display: grid; grid-template-rows: repeat(6, 15px); grid-template-columns: repeat(16, 15px); gap: 1px; height: 92px; align-content: start; }
            .road-box { width: 15px; height: 15px; display: flex; justify-content: center; align-items: center; position: relative; }

            .road-dot { width: 12px; height: 12px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 5px; font-weight: bold; color: #fff; position: relative; }
            .road-dot.p-solid { background: #3b82f6; }
            .road-dot.b-solid { background: #ef4444; }

            .tie-slash { position: absolute; width: 15px; height: 2px; background: #10b981; transform: rotate(-45deg); z-index: 5; pointer-events: none; }

            .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 100; justify-content: center; align-items: center; }
            .modal-content { background: #1c232a; width: 92%; max-height: 82vh; border-radius: 8px; padding: 15px; overflow-y: auto; border: 1px solid rgba(255,255,255,0.15); }
            .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px; font-size: 14px; font-weight: bold; }
            .close-modal { background: none; border: none; color: #fff; font-size: 18px; cursor: pointer; }
            .history-list { font-size: 11px; display: flex; flex-direction: column; gap: 6px; }
            .history-item { background: rgba(255,255,255,0.05); padding: 8px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; }

            .chip-picker-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 100; justify-content: center; align-items: center; }
            .chip-picker-box { background: #1e293b; padding: 15px; border-radius: 10px; width: 85%; text-align: center; border: 1px solid #475569; }
            .chip-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 15px 0; }
            .picker-chip { width: 45px; height: 45px; border-radius: 50%; margin: auto; display: flex; justify-content: center; align-items: center; font-weight: bold; font-size: 11px; cursor: pointer; border: 2px solid #fff; background: #3b82f6; }
        </style>
    </head>
    <body>
        <div class="top-bar">
            <div class="top-left">
                <button class="btn-exit" onclick="alert('Đã thoát bàn thành công!')">← <span>返回</span></button>
                <div class="balance-box" onclick="openHistoryModal()">
                    <span>$</span> <span id="user-balance">0.00</span>
                </div>
            </div>
            <div class="top-right">
                <span style="font-size:11px; color:#cbd5e1;">📶 🔊 ⚙️ 🔲</span>
            </div>
        </div>

        <div class="dealer-screen">
            <img src="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=800&q=80" alt="Dealer Live">
            <div class="table-info-overlay">
                <div id="table-name" style="font-weight: bold;">B11 BACCARAT</div>
                <div style="font-size: 8px; color: #aaa;" id="table-id-code">GB65EF638FDA</div>
            </div>
            <div class="time-box">
                <div id="hanoi-time" style="font-weight: bold;">15:48 (UTC+07)</div>
                <div style="font-size: 8px; color: #aaa;">Hạn mức: 10~20000</div>
            </div>

            <div class="cards-on-table">
                <div class="table-side" id="p-cards-area">
                    <span style="font-size:9px; color:#38bdf8;">闲</span>
                    <div class="playing-card"><div class="card-inner"><div class="card-face card-back">?</div><div class="card-face card-front" id="p-card-0">?</div></div></div>
                    <div class="playing-card"><div class="card-inner"><div class="card-face card-back">?</div><div class="card-face card-front" id="p-card-1">?</div></div></div>
                </div>
                <div class="table-side" id="b-cards-area">
                    <span style="font-size:9px; color:#ef4444;">庄</span>
                    <div class="playing-card"><div class="card-inner"><div class="card-face card-back">?</div><div class="card-face card-front" id="b-card-0">?</div></div></div>
                    <div class="playing-card"><div class="card-inner"><div class="card-face card-back">?</div><div class="card-face card-front" id="b-card-1">?</div></div></div>
                </div>
            </div>
        </div>

        <div class="game-panel">
            <div class="round-info-bar">
                <span>Trạng thái: <strong id="game-status" style="color:#2ecc71;">Đang đặt cược</strong></span>
                <span style="background: rgba(0,0,0,0.4); padding: 2px 6px; border-radius: 10px; color: #facc15;" id="timer-val">⏳ 15s</span>
                <span>Hạn mức: 10~20000</span>
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
                <div class="menu-chip-btn" onclick="openChipPicker()">⚙️</div>
                <div class="chips-scroll" id="chips-bar-container">
                    <div class="chip c-10 selected" onclick="selectChip(10, this)">10</div>
                    <div class="chip c-20" onclick="selectChip(20, this)">20</div>
                    <div class="chip c-50" onclick="selectChip(50, this)">50</div>
                    <div class="chip c-100" onclick="selectChip(100, this)">100</div>
                    <div class="chip c-200" onclick="selectChip(200, this)">200</div>
                    <div class="chip c-2k" onclick="selectChip(2000, this)">2K</div>
                </div>
                <div class="commission-toggle" onclick="toggleCommission()">
                    <span style="color: #cbd5e1;">免佣</span>
                    <input type="checkbox" id="comm-checkbox" class="comm-input">
                    <label for="comm-checkbox" class="toggle-switch" style="pointer-events: none;"></label>
                </div>
            </div>
        </div>

        <!-- BẢNG SOI CẦU: ĐÚNG 6 HÀNG DỌC, CỐ ĐỊNH BIG ROAD BẮT ĐẦU TỪ CỘT 8 -->
        <div class="scoreboard-section">
            <div class="sc-header-row">
                <div class="sc-stats-group">
                    <div class="stat-item"><span class="ratio-pie" id="ratio-pie-circle"></span><span id="stat-total">0</span></div>
                    <div class="stat-item"><span class="stat-icon-circle" style="background: #ef4444;"></span><span id="stat-b">0</span></div>
                    <div class="stat-item"><span class="stat-icon-circle" style="background: #3b82f6;"></span><span id="stat-p">0</span></div>
                    <div class="stat-item"><span class="stat-icon-circle" style="background: #10b981;"></span><span id="stat-t">0</span></div>
                    <div class="stat-item"><span class="stat-icon-circle" style="background: #ef4444; border:1px solid #facc15; font-size:5px; display:flex; justify-content:center; align-items:center; color:#fff;">6</span><span id="stat-b6">0</span></div>
                    <div class="stat-item"><span class="stat-icon-circle" style="background: #3b82f6; border:1px solid #facc15; font-size:5px; display:flex; justify-content:center; align-items:center; color:#fff;">7</span><span id="stat-p7">0</span></div>
                </div>

                <div class="sc-menus">
                    <div class="sc-menu-item">
                        <div class="sc-menu-icons"><span style="width:4px; height:4px; background:#3b82f6; border-radius:50%;"></span><span style="width:4px; height:4px; background:#ef4444; border-radius:50%;"></span><span style="width:3px; height:3px; background:#ef4444; transform:rotate(45deg); display:inline-block;"></span></div>
                        <span>庄问路</span>
                    </div>
                    <div class="sc-menu-item">
                        <div class="sc-menu-icons"><span style="width:4px; height:4px; background:#ef4444; border-radius:50%;"></span><span style="width:4px; height:4px; background:#3b82f6; border-radius:50%;"></span><span style="width:3px; height:3px; background:#3b82f6; transform:rotate(45deg); display:inline-block;"></span></div>
                        <span>闲问路</span>
                    </div>
                    <div class="sc-menu-item" style="background: rgba(239,68,68,0.2); border: 1px solid #ef4444;">
                        <span style="font-weight:bold; color:#f87171;">📋 好路 (Ván: <span id="round-count">0</span>)</span>
                    </div>
                </div>
            </div>

            <div class="road-tables-container">
                <!-- Bảng trái Bead Plate: Đúng 7 cột, đủ 6 hàng dọc -->
                <div class="bead-grid-table" id="bead-plate-container"></div>
                <!-- Bảng phải Big Road: Bắt đầu vẽ từ cột số 8 (index 7), cố định 16 cột -->
                <div class="road-grid-table" id="big-road-container"></div>
            </div>
        </div>

        <div class="modal" id="history-modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Lịch sử đặt cược</h3>
                    <button class="close-modal" onclick="closeHistoryModal()">✕</button>
                </div>
                <div class="history-list" id="history-list-content">
                    <div>Chưa có lịch sử giao dịch.</div>
                </div>
            </div>
        </div>

        <div class="chip-picker-modal" id="chip-picker-modal">
            <div class="chip-picker-box">
                <h3 style="margin-bottom: 10px; font-size:14px;">Chọn mệnh giá chip</h3>
                <div class="chip-grid">
                    <div class="picker-chip" onclick="setCustomChip(500)">500</div>
                    <div class="picker-chip" onclick="setCustomChip(1000)">1K</div>
                    <div class="picker-chip" onclick="setCustomChip(3000)">3K</div>
                    <div class="picker-chip" onclick="setCustomChip(5000)">5K</div>
                    <div class="picker-chip" onclick="setCustomChip(10000)">10K</div>
                    <div class="picker-chip" onclick="setCustomChip(15000)">15K</div>
                    <div class="picker-chip" onclick="setCustomChip(20000)">20K</div>
                </div>
                <button onclick="closeChipPicker()" style="background:#ef4444; border:none; color:#fff; padding:5px 15px; border-radius:4px; font-size:12px; cursor:pointer;">Đóng</button>
            </div>
        </div>

        <script>
            let balance = 0.0;
            let selectedChip = 10;
            let isCommissionFree = false;
            let currentBets = { player: 0, banker: 0, tie: 0, player_pair: 0, banker_pair: 0, lucky_7: 0, super_lucky_7: 0, lucky_6: 0 };
            let historyList = [];

            // Đổi phiên bản v10 để xóa sạch hoàn toàn bộ nhớ đệm cũ gây lỗi lệch cột
            let globalGame = JSON.parse(localStorage.getItem('baccarat_global_game_8decks_v10') || 'null');
            if (!globalGame) {
                globalGame = {
                    scoreRecords: [],
                    totalRounds: 0,
                    statsCount: { total: 0, b: 0, p: 0, t: 0, b6: 0, p7: 0 },
                    shoe: generateShoe()
                };
            }

            function generateShoe() {
                let deck = [];
                const suits = ['♠', '♣', '♥', '♦'];
                const vals = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'];
                for (let i = 0; i < 8; i++) {
                    for (let s of suits) {
                        for (let v of vals) {
                            deck.push({ text: v + s, color: (s === '♥' || s === '♦') ? 'red' : '' });
                        }
                    }
                }
                for (let i = deck.length - 1; i > 0; i--) {
                    let j = Math.floor(Math.random() * (i + 1));
                    [deck[i], deck[j]] = [deck[j], deck[i]];
                }
                return deck;
            }

            if (!globalGame.shoe || globalGame.shoe.length < 10) {
                globalGame.shoe = generateShoe();
            }

            let timeLeft = 15;
            let gamePhase = 'betting';

            function saveGlobalGame() {
                localStorage.setItem('baccarat_global_game_8decks_v10', JSON.stringify(globalGame));
            }

            function generateUniqueTable() {
                let randHex = Math.random().toString(16).substring(2, 10).toUpperCase();
                document.getElementById('table-id-code').innerText = 'GB' + randHex + 'DA';
            }
            generateUniqueTable();

            updateStatsDisplay();
            renderScoreboard();
            document.getElementById('round-count').innerText = globalGame.totalRounds;

            setInterval(() => {
                let now = new Date();
                let utc = now.getTime() + (now.getTimezoneOffset() * 60000);
                let hanoiTime = new Date(utc + (3600000 * 7));
                let h = String(hanoiTime.getHours()).padStart(2, '0');
                let m = String(hanoiTime.getMinutes()).padStart(2, '0');
                let s = String(hanoiTime.getSeconds()).padStart(2, '0');
                document.getElementById('hanoi-time').innerText = `${h}:${m}:${s} (UTC+07)`;
            }, 1000);

            setInterval(() => {
                if (gamePhase === 'betting') {
                    timeLeft--;
                    document.getElementById('timer-val').innerText = `⏳ ${timeLeft}s`;
                    if (timeLeft <= 0) {
                        gamePhase = 'dealing';
                        document.getElementById('game-status').innerText = 'Đang mở bài...';
                        document.getElementById('game-status').style.color = '#e74c3c';
                        startRandomDealing();
                    }
                }
            }, 1000);

            function startRandomDealing() {
                if (globalGame.shoe.length < 10) {
                    globalGame.shoe = generateShoe();
                }
                let p1 = globalGame.shoe.pop();
                let p2 = globalGame.shoe.pop();
                let b1 = globalGame.shoe.pop();
                let b2 = globalGame.shoe.pop();

                document.getElementById('p-card-0').innerText = p1.text;
                document.getElementById('p-card-0').className = `card-face card-front ${p1.color}`;
                document.getElementById('p-card-1').innerText = p2.text;
                document.getElementById('p-card-1').className = `card-face card-front ${p2.color}`;

                document.getElementById('b-card-0').innerText = b1.text;
                document.getElementById('b-card-0').className = `card-face card-front ${b1.color}`;
                document.getElementById('b-card-1').innerText = b2.text;
                document.getElementById('b-card-1').className = `card-face card-front ${b2.color}`;

                let pCardsEl = document.getElementById('p-cards-area').querySelectorAll('.playing-card');
                let bCardsEl = document.getElementById('b-cards-area').querySelectorAll('.playing-card');

                setTimeout(() => pCardsEl[0].classList.add('flipped'), 300);
                setTimeout(() => pCardsEl[1].classList.add('flipped'), 900);
                setTimeout(() => bCardsEl[0].classList.add('flipped'), 1500);
                setTimeout(() => bCardsEl[1].classList.add('flipped'), 2100);

                setTimeout(() => {
                    let pScore = (getCardVal(p1.text) + getCardVal(p2.text)) % 10;
                    let bScore = (getCardVal(b1.text) + getCardVal(b2.text)) % 10;

                    let winner = 'B';
                    if (pScore > bScore) winner = 'P';
                    else if (pScore === bScore) winner = 'T';

                    let recordType = winner;
                    if (winner === 'P' && pScore === 7) recordType = 'P7';
                    if (winner === 'B' && bScore === 6) recordType = 'B6';

                    globalGame.statsCount.total++;
                    if (winner === 'B') globalGame.statsCount.b++;
                    if (winner === 'P') globalGame.statsCount.p++;
                    if (winner === 'T') globalGame.statsCount.t++;
                    if (recordType === 'B6') globalGame.statsCount.b6++;
                    if (recordType === 'P7') globalGame.statsCount.p7++;

                    globalGame.scoreRecords.push(recordType);
                    globalGame.totalRounds++;
                    saveGlobalGame();

                    updateStatsDisplay();
                    document.getElementById('round-count').innerText = globalGame.totalRounds;
                    renderScoreboard();

                    resolveBets(winner);

                    gamePhase = 'betting';
                    timeLeft = 15;
                    document.getElementById('game-status').innerText = 'Đang đặt cược';
                    document.getElementById('game-status').style.color = '#2ecc71';
                    resetTableCards();
                }, 3000);
            }

            function getCardVal(cardStr) {
                let v = cardStr.slice(0, -1);
                if (['10', 'J', 'Q', 'K'].includes(v)) return 0;
                if (v === 'A') return 1;
                return parseInt(v);
            }

            function resetTableCards() {
                document.querySelectorAll('.playing-card').forEach(c => c.classList.remove('flipped'));
                document.querySelectorAll('.card-front').forEach(c => { c.innerText = '?'; });
            }

            function updateStatsDisplay() {
                document.getElementById('stat-total').innerText = globalGame.statsCount.total;
                document.getElementById('stat-b').innerText = globalGame.statsCount.b;
                document.getElementById('stat-p').innerText = globalGame.statsCount.p;
                document.getElementById('stat-t').innerText = globalGame.statsCount.t;
                document.getElementById('stat-b6').innerText = globalGame.statsCount.b6;
                document.getElementById('stat-p7').innerText = globalGame.statsCount.p7;

                let total = globalGame.statsCount.total;
                let pieEl = document.getElementById('ratio-pie-circle');
                if (total === 0) {
                    pieEl.style.background = '#334155';
                } else {
                    let bAngle = (globalGame.statsCount.b / total) * 360;
                    let pAngle = bAngle + (globalGame.statsCount.p / total) * 360;
                    pieEl.style.background = `conic-gradient(#ef4444 0deg ${bAngle}deg, #3b82f6 ${bAngle}deg ${pAngle}deg, #10b981 ${pAngle}deg 360deg)`;
                }
            }

            function selectChip(val, el) {
                document.querySelectorAll('.chip').forEach(c => c.classList.remove('selected'));
                el.classList.add('selected');
                selectedChip = val;
            }

            function openChipPicker() { document.getElementById('chip-picker-modal').style.display = 'flex'; }
            function closeChipPicker() { document.getElementById('chip-picker-modal').style.display = 'none'; }
            function setCustomChip(val) {
                selectedChip = val;
                closeChipPicker();
                let bar = document.getElementById('chips-bar-container');
                bar.innerHTML += `<div class="chip selected" onclick="selectChip(${val}, this)">${val >= 1000 ? (val/1000)+'K' : val}</div>`;
            }

            function toggleCommission() {
                let cb = document.getElementById('comm-checkbox');
                cb.checked = !cb.checked;
                isCommissionFree = cb.checked;
                document.getElementById('rate-banker').innerText = isCommissionFree ? '1 : 1' : '1 : 0.95';
            }

            function placeBet(type) {
                if (gamePhase !== 'betting') {
                    alert('Hết thời gian đặt cược!');
                    return;
                }
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
            }

            function cancelBets() {
                if (gamePhase !== 'betting') return;
                let refund = Object.values(currentBets).reduce((a, b) => a + b, 0);
                balance += refund;
                currentBets = { player: 0, banker: 0, tie: 0, player_pair: 0, banker_pair: 0, lucky_7: 0, super_lucky_7: 0, lucky_6: 0 };
                document.getElementById('user-balance').innerText = balance.toFixed(2);
                ['player', 'banker', 'tie', 'player_pair', 'banker_pair', 'lucky_7', 'super_lucky_7', 'lucky_6'].forEach(t => {
                    document.getElementById(`amt-${t}`).style.display = 'none';
                });
            }

            function doubleBets() {
                if (gamePhase !== 'betting') return;
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

            function resolveBets(winner) {
                let totalBet = Object.values(currentBets).reduce((a, b) => a + b, 0);
                if (totalBet === 0) return;

                let payout = 0;
                let winDesc = '';
                if (winner === 'P' && currentBets.player > 0) {
                    payout += currentBets.player * 2;
                    winDesc += `Thắng Player (+${currentBets.player * 1}) `;
                }
                if (winner === 'B' && currentBets.banker > 0) {
                    let rate = isCommissionFree ? 2 : 1.95;
                    payout += currentBets.banker * rate;
                    winDesc += `Thắng Banker (+${currentBets.banker * (rate-1)}) `;
                }
                if (winner === 'T' && currentBets.tie > 0) {
                    payout += currentBets.tie * 9;
                    winDesc += `Thắng Tie (+${currentBets.tie * 8}) `;
                }
                if (winner === 'T') {
                    payout += currentBets.player + currentBets.banker;
                }

                let profit = payout - totalBet;
                balance += payout;
                document.getElementById('user-balance').innerText = balance.toFixed(2);

                historyList.unshift({
                    time: new Date().toLocaleTimeString(),
                    result: winner,
                    bet: totalBet,
                    profit: profit,
                    desc: winDesc || 'Thua cược'
                });

                currentBets = { player: 0, banker: 0, tie: 0, player_pair: 0, banker_pair: 0, lucky_7: 0, super_lucky_7: 0, lucky_6: 0 };
                ['player', 'banker', 'tie', 'player_pair', 'banker_pair', 'lucky_7', 'super_lucky_7', 'lucky_6'].forEach(t => {
                    let tag = document.getElementById(`amt-${t}`);
                    if(tag) tag.style.display = 'none';
                });
            }

            function renderScoreboard() {
                // 1. Bảng Bead Plate bên trái: Đúng 7 cột, đủ 6 hàng dọc
                let beadContainer = document.getElementById('bead-plate-container');
                beadContainer.innerHTML = '';
                globalGame.scoreRecords.forEach(rec => {
                    let box = document.createElement('div');
                    box.className = 'bead-box';
                    let div = document.createElement('div');
                    if (rec === 'P7') {
                        div.className = 'bead P7'; div.innerText = '7';
                    } else if (rec === 'B6') {
                        div.className = 'bead B6'; div.innerText = '6';
                    } else {
                        div.className = `bead ${rec.charAt(0)}`; div.innerText = rec === 'T' ? 'T' : rec.charAt(0);
                    }
                    box.appendChild(div);
                    beadContainer.appendChild(box);
                });

                // 2. Bảng Big Road bên phải: LUÔN BẮT ĐẦU TỪ CỘT THỨ 8 (index 7), cố định 16 cột hiển thị
                let bigRoadContainer = document.getElementById('big-road-container');
                bigRoadContainer.innerHTML = '';
                
                let rawMatrix = Array(6).fill(0).map(() => Array(50).fill(null));
                let col = 7, row = 0;
                let lastType = null;
                let lastCellRef = null;

                globalGame.scoreRecords.forEach(rec => {
                    let base = rec.startsWith('P') ? 'P' : (rec.startsWith('B') ? 'B' : 'T');
                    if (base === 'T') {
                        if (lastCellRef) lastCellRef.tieCount = (lastCellRef.tieCount || 0) + 1;
                        return;
                    }

                    if (lastType === null) {
                        let cell = { type: rec, base: base, tieCount: 0 };
                        rawMatrix[row][col] = cell;
                        lastCellRef = cell;
                        lastType = base;
                    } else if (base === lastType) {
                        if (row + 1 < 6 && rawMatrix[row + 1][col] === null) {
                            row++;
                        } else {
                            col++;
                        }
                        let cell = { type: rec, base: base, tieCount: 0 };
                        rawMatrix[row][col] = cell;
                        lastCellRef = cell;
                    } else {
                        col = 7;
                        while (rawMatrix[0][col] !== null) col++;
                        row = 0;
                        let cell = { type: rec, base: base, tieCount: 0 };
                        rawMatrix[row][col] = cell;
                        lastCellRef = cell;
                        lastType = base;
                    }
                });

                let maxCol = 7;
                for (let c = 7; c < 50; c++) {
                    for (let r = 0; r < 6; r++) {
                        if (rawMatrix[r][c] !== null) maxCol = c;
                    }
                }

                let startCol = 7;
                if (maxCol >= 7 + 16) {
                    startCol = maxCol - 15;
                }

                for (let c = startCol; c < startCol + 16; c++) {
                    for (let r = 0; r < 6; r++) {
                        let box = document.createElement('div');
                        box.className = 'road-box';
                        let cell = rawMatrix[r][c];
                        if (cell) {
                            let dot = document.createElement('div');
                            dot.className = `road-dot ${cell.base.toLowerCase()}-solid`;
                            if (cell.type === 'P7') dot.innerText = '7';
                            if (cell.type === 'B6') dot.innerText = '6';
                            for (let i = 0; i < cell.tieCount; i++) {
                                let slash = document.createElement('div');
                                slash.className = 'tie-slash';
                                dot.appendChild(slash);
                            }
                            box.appendChild(dot);
                        }
                        bigRoadContainer.appendChild(box);
                    }
                }
            }

            function openHistoryModal() {
                document.getElementById('history-modal').style.display = 'flex';
                let listEl = document.getElementById('history-list-content');
                if (historyList.length === 0) {
                    listEl.innerHTML = `<div>Chưa có lịch sử giao dịch đặt cược.</div>`;
                } else {
                    listEl.innerHTML = historyList.map(h => `
                        <div class="history-item">
                            <span>[${h.time}] Kết quả: <b>${h.result}</b> | Cược: $${h.bet}</span>
                            <span style="color: ${h.profit >= 0 ? '#22c55e' : '#ef4444'};">${h.profit >= 0 ? '+' : ''}$${h.profit.toFixed(2)}</span>
                        </div>
                    `).join('');
                }
            }
            function closeHistoryModal() { document.getElementById('history-modal').style.display = 'none'; }
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
        
        print("🤖 Bot Telegram tích hợp Baccarat hoàn hảo đã khởi chạy...")
        app.run_polling()
