import json
import random
import sqlite3
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI()

# Phục vụ file giao diện HTML
app.mount("/static", StaticFiles(directory="static"), name="static")

def init_db():
    conn = sqlite3.connect('game_pro.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 1000
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_user_coins(user_id, username):
    conn = sqlite3.connect('game_pro.db')
    cursor = conn.cursor()
    cursor.execute('SELECT coins FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute('INSERT INTO users (user_id, username, coins) VALUES (?, ?, 1000)', (user_id, username or "Player"))
        conn.commit()
        coins = 1000
    else:
        coins = row[0]
    conn.close()
    return coins

def update_user_coins(user_id, amount):
    conn = sqlite3.connect('game_pro.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

# Quản lý kết nối WebSocket thời gian thực
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_text(json.dumps(message))

manager = ConnectionManager()

@app.get("/")
async def get_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# Xử lý ván Baccarat ngẫu nhiên
def play_baccarat():
    p_pts = random.randint(0, 9)
    b_pts = random.randint(0, 9)
    if p_pts > b_pts:
        winner = "player"
    elif b_pts > p_pts:
        winner = "banker"
    else:
        winner = "tie"
    return p_pts, b_pts, winner

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            packet = json.loads(data)
            
            action = packet.get("action")
            user_id = packet.get("user_id")
            username = packet.get("username", "Player")

            if action == "get_balance":
                coins = get_user_coins(user_id, username)
                await websocket.send_text(json.dumps({"type": "balance", "coins": coins}))

            elif action == "bet_and_play":
                choice = packet.get("choice") # player, banker, tie
                bet_amount = packet.get("amount", 100)
                
                coins = get_user_coins(user_id, username)
                if coins < bet_amount:
                    await websocket.send_text(json.dumps({"type": "error", "message": "Bạn không đủ xu ảo!"}))
                    continue

                # Trừ xu đặt cược
                update_user_coins(user_id, -bet_amount)
                
                # Chia bài & lật
                p_pts, b_pts, winner = play_baccarat()
                
                # Tính thưởng xu ảo
                win_amount = 0
                if choice == winner:
                    if winner == "player": win_amount = bet_amount * 2
                    elif winner == "banker": win_amount = int(bet_amount * 1.95)
                    elif winner == "tie": win_amount = bet_amount * 9
                    update_user_coins(user_id, win_amount)

                new_coins = get_user_coins(user_id, username)
                
                await websocket.send_text(json.dumps({
                    "type": "result",
                    "p_pts": p_pts,
                    "b_pts": b_pts,
                    "winner": winner,
                    "choice": choice,
                    "win_amount": win_amount,
                    "new_coins": new_coins
                }))

    except WebSocketDisconnect:
        manager.disconnect(websocket)