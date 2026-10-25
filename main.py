import sqlite3
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Khởi tạo Database SQLite
def init_db():
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

class DealRequest(BaseModel):
    bets: dict
    telegram_id: str = "default_user"

# API lấy số dư thực tế từ Database
@app.get("/api/user/{telegram_id}")
async def get_user_balance(telegram_id: str):
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute("INSERT INTO users (telegram_id, balance) VALUES (?, ?)", (telegram_id, 0))
        conn.commit()
        balance = 0
    else:
        balance = row[0]
    conn.close()
    return {"balance": balance}

# API xử lý ván cược tự động
@app.post("/api/deal")
async def deal_game(req: DealRequest):
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    
    # Lấy số dư hiện tại của user
    cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (req.telegram_id,))
    row = cursor.fetchone()
    current_balance = row[0] if row else 0
    
    # Tính tổng tiền cược
    total_bet = sum(req.bets.values())
    if current_balance < total_bet:
        conn.close()
        return {"error": "Không đủ số dư!"}
    
    # Trừ tiền cược ngay khi vào ván
    current_balance -= total_bet
    
    # Logic chia bài Baccarat chuẩn
    import random
    def get_val(c): return 0 if c in ['J','Q','K','10'] else (1 if c=='A' else int(c))
    deck = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']
    
    p_cards = [random.choice(deck), random.choice(deck)]
    b_cards = [random.choice(deck), random.choice(deck)]
    p_score = sum(get_val(c) for c in p_cards) % 10
    b_score = sum(get_val(c) for c in b_cards) % 10

    if p_score <= 5:
        p_cards.append(random.choice(deck))
        p_score = sum(get_val(c) for c in p_cards) % 10
    if b_score <= 5:
        b_cards.append(random.choice(deck))
        b_score = sum(get_val(c) for c in b_cards) % 10

    winner = 'T'
    if p_score > b_score: winner = 'P'
    elif b_score > p_score: winner = 'B'

    # Tính tiền thắng trả về
    payout = 0
    for b_type, amt in req.bets.items():
        if b_type == 'PLAYER' and winner == 'P': payout += amt * 2
        elif b_type == 'BANKER' and winner == 'B': payout += int(amt * 1.95)
        elif b_type == 'TIE' and winner == 'T': payout += amt * 9

    current_balance += payout
    
    # Cập nhật lại vào DB
    cursor.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (current_balance, req.telegram_id))
    conn.commit()
    conn.close()

    return {
        "player_cards": p_cards, "banker_cards": b_cards,
        "player_score": p_score, "banker_score": b_score,
        "winner_code": winner, "new_balance": current_balance
    }
