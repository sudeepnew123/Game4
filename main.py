from flask import Flask, request
import os, random, requests
from tinydb import TinyDB, Query

app = Flask(__name__)
TOKEN = os.environ.get("BOT_TOKEN")
BOT_URL = f"https://api.telegram.org/bot{TOKEN}"

db = TinyDB("users.json")
User = Query()
games = {}

def get_user(user_id, name):
    user = db.get(User.id == user_id)
    if not user:
        db.insert({"id": user_id, "name": name, "coins": 100})
        return {"id": user_id, "name": name, "coins": 100}
    return user

def update_coins(user_id, coins):
    db.update({"coins": coins}, User.id == user_id)

def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = reply_markup
    requests.post(f"{BOT_URL}/sendMessage", json=data)

def edit_message(chat_id, msg_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": msg_id, "text": text}
    if reply_markup:
        data["reply_markup"] = reply_markup
    requests.post(f"{BOT_URL}/editMessageText", json=data)

def build_grid(user_id, reveal_all=False):
    btns = []
    for i in range(5):
        row = []
        for j in range(5):
            idx = i * 5 + j
            if reveal_all:
                if idx in games[user_id]['bombs']:
                    label = "💣"
                elif idx in games[user_id]['opened']:
                    label = "💎"
                else:
                    label = "🔲"
            else:
                label = "❓" if idx not in games[user_id]['opened'] else (
                    "💎" if idx not in games[user_id]['bombs'] else "💣"
                )
            row.append({'text': label, 'callback_data': f"tap:{idx}"})
        btns.append(row)
    if not reveal_all and games[user_id]['status'] == 'playing':
        btns.append([{'text': "💸 Cashout", 'callback_data': 'cashout'}])
    return {'inline_keyboard': btns}

def start_game(user_id, amount, mines):
    cells = list(range(25))
    bombs = set(random.sample(cells, mines))
    games[user_id] = {
        'bombs': bombs, 'opened': set(),
        'bet': amount, 'mines': mines,
        'status': 'playing'
    }

@app.route("/", methods=["POST"])
def webhook():
    update = request.get_json()

    if "message" in update:
        msg = update["message"]
        text = msg.get("text", "")
        chat_id = msg["chat"]["id"]
        user = msg["from"]
        user_id = user["id"]
        name = user.get("first_name", "Player")
        user_data = get_user(user_id, name)

        if text.startswith("/start"):
            send_message(chat_id, f"Welcome {name}! You have 100 coins.\nUse /mine <amount> <mines> to start playing!")

        elif text.startswith("/balance"):
            send_message(chat_id, f"{name}, you have {user_data['coins']} coins.")

        elif text.startswith("/mine"):
            parts = text.split()
            if len(parts) != 3:
                send_message(chat_id, "Usage: /mine <amount> <mines>")
                return {"ok": True}
            try:
                amount = int(parts[1])
                mines = int(parts[2])
                if amount < 10 or mines < 1 or mines >= 25:
                    send_message(chat_id, "Min 10 coins, mines 1–24.")
                    return {"ok": True}
                if user_data['coins'] < amount:
                    send_message(chat_id, "Insufficient coins.")
                    return {"ok": True}
                start_game(user_id, amount, mines)
                update_coins(user_id, user_data['coins'] - amount)
                send_message(chat_id, f"{name}'s game started!\nTap tiles:", reply_markup=build_grid(user_id))
            except:
                send_message(chat_id, "Invalid format. Use: /mine 50 3")

    elif "callback_query" in update:
        query = update["callback_query"]
        data = query["data"]
        user = query["from"]
        user_id = user["id"]
        chat_id = query["message"]["chat"]["id"]
        msg_id = query["message"]["message_id"]
        name = user.get("first_name", "Player")
        user_data = get_user(user_id, name)

        if user_id not in games or games[user_id]['status'] != 'playing':
            send_message(chat_id, "No active game.")
            return {"ok": True}

        if data.startswith("tap:"):
            idx = int(data.split(":")[1])
            if idx in games[user_id]['opened']:
                return {"ok": True}

            if idx in games[user_id]['bombs']:
                games[user_id]['opened'].add(idx)
                games[user_id]['status'] = 'lost'
                edit_message(chat_id, msg_id, "💥 Boom! You hit a bomb!\nGame Over!", reply_markup=build_grid(user_id, reveal_all=True))
            else:
                games[user_id]['opened'].add(idx)
                edit_message(chat_id, msg_id, "Nice! Tap more or cashout:", reply_markup=build_grid(user_id))

        elif data == "cashout":
            opened = len(games[user_id]['opened'])
            bet = games[user_id]['bet']
            if opened == 0:
                reward = 0
            else:
                multiplier = round(1 + (opened * 0.3), 2)
                reward = int(bet * multiplier)
            update_coins(user_id, user_data['coins'] + reward)
            games[user_id]['status'] = 'cashed'
            edit_message(chat_id, msg_id, f"💸 Cashed out!\nGems: {opened}\nEarned: {reward} coins", reply_markup=build_grid(user_id, reveal_all=True))

    return {"ok": True}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
