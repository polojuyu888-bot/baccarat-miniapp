import random
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

class DealRequest(BaseModel):
    bets: dict
    initData: str = None

def get_card_value(card):
    if card in ['J', 'Q', 'K', '10']:
        return 0
    if card == 'A':
        return 1
    return int(card)

def draw_card():
    cards = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    return random.choice(cards)

@app.post("/api/deal")
async def deal_game(req: DealRequest):
    # Chia 2 lá đầu tiên cho Player và Banker
    p_cards = [draw_card(), draw_card()]
    b_cards = [draw_card(), draw_card()]

    p_score = sum(get_card_value(c) for c in p_cards) % 10
    b_score = sum(get_card_value(c) for c in b_cards) % 10

    # Quy tắc rút bài thứ 3
    if p_score <= 5:
        p_cards.append(draw_card())
        p_score = sum(get_card_value(c) for c in p_cards) % 10

    if b_score <= 5:
        b_cards.append(draw_card())
        b_score = sum(get_card_value(c) for c in b_cards) % 10

    # Phân định thắng thua
    winner_code = 'T'
    if p_score > b_score:
        winner_code = 'P'
    elif b_score > p_score:
        winner_code = 'B'

    # Giả lập cộng/trừ xu
    payout = 0
    for bet_type, amount in req.bets.items():
        if bet_type == 'PLAYER' and winner_code == 'P':
            payout += amount * 2
        elif bet_type == 'BANKER' and winner_code == 'B':
            payout += int(amount * 1.95)
        elif bet_type == 'TIE' and winner_code == 'T':
            payout += amount * 9

    return {
        "player_cards": p_cards,
        "banker_cards": b_cards,
        "player_score": p_score,
        "banker_score": b_score,
        "winner_code": winner_code,
        "new_balance": 100000 + payout
    }
