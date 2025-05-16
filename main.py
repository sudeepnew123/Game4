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

def help_text():
    return """🎮 *Mines Game Bot Help* 🎮

*Basic Commands:*
/start - Initialize your account
/help - Show this help message
/balance - Check your Hiwa balance
/mine <amount> <mines> - Start a new game (e.g., /mine 10 5)
/cashout - Cash out your current winnings
/daily - Claim daily bonus (24h cooldown)
/weekly - Claim weekly bonus (7d cooldown)
/leaderboard - Show top players
/gift @username <amount> - Send Hiwa to another player

*New Features:*
/store - View and buy emojis
/collection - View your owned emojis
/give emoji - Gift an emoji (reply to user)

*Game Rules:*
1. 5x5 grid with hidden gems (💎) and bombs (💣)
2. Choose how many bombs (3-24) when starting
3. Reveal tiles to find gems
4. Cash out after finding at least 2 gems
5. Hit a bomb and you lose your bet

(Admin commands in Part 2...)
"""

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

        elif text.startswith("/help"):
            send_message(chat_id, help_text(), {"parse_mode": "Markdown"})

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

    return {"ok": True}

def start_game(user_id, amount, mines):
    bomb_positions = random.sample(range(25), mines)
    games[user_id] = {
        "amount": amount,
        "mines": mines,
        "bombs": bomb_positions,
        "revealed": [],
        "gems_found": 0
    }

def build_grid(user_id):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton  # Only if using `python-telegram-bot`, else use JSON
    game = games.get(user_id)
    if not game:
        return
    buttons = []
    for row in range(5):
        btn_row = []
        for col in range(5):
            idx = row * 5 + col
            if idx in game["revealed"]:
                btn_row.append({"text": "💎", "callback_data": f"noop"})
            else:
                btn_row.append({"text": " ", "callback_data": f"reveal_{idx}"})
        buttons.append(btn_row)
    return {"inline_keyboard": buttons}

def reveal_tile(user_id, index):
    game = games.get(user_id)
    if not game or index in game["revealed"]:
        return None

    if index in game["bombs"]:
        result = reveal_all_bombs(game)
        del games[user_id]
        return "💥 BOOM! You hit a bomb!\n" + result

    game["revealed"].append(index)
    game["gems_found"] += 1
    if game["gems_found"] >= 2:
        return f"You found a 💎! Type /cashout to secure your winnings."
    return "You found a 💎!"

def reveal_all_bombs(game):
    bomb_map = ["💣" if i in game["bombs"] else "💎" for i in range(25)]
    grid = ""
    for i in range(5):
        grid += " ".join(bomb_map[i*5:(i+1)*5]) + "\n"
    return "*Bomb Map:*\n" + grid

@app.route("/callback", methods=["POST"])
def callback_handler():
    data = request.get_json()
    query = data["callback_query"]
    user_id = query["from"]["id"]
    chat_id = query["message"]["chat"]["id"]
    data_str = query["data"]

    if data_str.startswith("reveal_"):
        index = int(data_str.split("_")[1])
        result = reveal_tile(user_id, index)
        send_message(chat_id, result)

    return {"ok": True}

@app.route("/admin", methods=["POST"])
def admin_commands():
    update = request.get_json()
    msg = update["message"]
    text = msg.get("text", "")
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    
    # Replace with your own Telegram user ID
    ADMIN_ID = 6356015122

    if user_id != ADMIN_ID:
        send_message(chat_id, "You're not authorized.")
        return {"ok": True}

    if text.startswith("/broadcast"):
        msg_text = text[len("/broadcast "):]
        for user in db:
            send_message(user["id"], msg_text)
        send_message(chat_id, "Broadcast sent.")

    elif text.startswith("/resetdata"):
        db.truncate()
        send_message(chat_id, "All user data reset.")

    elif text.startswith("/setbalance"):
        parts = text.split()
        if len(parts) == 3:
            username = parts[1].lstrip("@")
            amount = int(parts[2])
            for u in db:
                if u["name"] == username:
                    update_coins(u["id"], amount)
                    send_message(chat_id, f"{username}'s balance updated.")
                    break
    return {"ok": True}

from datetime import datetime, timedelta

def get_now():
    return datetime.now().isoformat()

def can_claim(user, key, days=1):
    last = user.get(key)
    if not last:
        return True
    last_time = datetime.fromisoformat(last)
    return datetime.now() - last_time >= timedelta(days=days)

@app.route("/bonus", methods=["POST"])
def bonus_handler():
    update = request.get_json()
    msg = update["message"]
    text = msg.get("text", "")
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    name = msg["from"].get("first_name", "Player")
    user = get_user(user_id, name)

    if text == "/daily":
        if can_claim(user, "last_daily", 1):
            user["coins"] += 50
            user["last_daily"] = get_now()
            db.update(user, User.id == user_id)
            send_message(chat_id, "You claimed 50 coins for daily reward!")
        else:
            send_message(chat_id, "Come back tomorrow for daily bonus!")

    elif text == "/weekly":
        if can_claim(user, "last_weekly", 7):
            user["coins"] += 200
            user["last_weekly"] = get_now()
            db.update(user, User.id == user_id)
            send_message(chat_id, "You claimed 200 coins for weekly reward!")
        else:
            send_message(chat_id, "Weekly bonus already claimed.")

    elif text == "/leaderboard":
        all_users = db.all()
        top = sorted(all_users, key=lambda x: x["coins"], reverse=True)[:10]
        lb = "\n".join([f"{i+1}. {u['name']} - {u['coins']} coins" for i, u in enumerate(top)])
        send_message(chat_id, "*Leaderboard:*\n" + lb, {"parse_mode": "Markdown"})

    elif text.startswith("/gift"):
        parts = text.split()
        if len(parts) != 3 or not parts[2].isdigit():
            send_message(chat_id, "Usage: /gift @username <amount>")
            return {"ok": True}
        username = parts[1].lstrip("@")
        amount = int(parts[2])
        if user["coins"] < amount:
            send_message(chat_id, "Not enough coins to gift.")
            return {"ok": True}
        for u in db:
            if u["name"] == username:
                user["coins"] -= amount
                u["coins"] += amount
                db.update(user, User.id == user_id)
                db.update(u, User.id == u["id"])
                send_message(chat_id, f"Gifted {amount} coins to {username}.")
                break
        else:
            send_message(chat_id, "User not found.")

    return {"ok": True}

EMOJI_STORE = {
    "💎": 100,
    "🔥": 200,
    "👑": 300
}

@app.route("/emoji", methods=["POST"])
def emoji_handler():
    update = request.get_json()
    msg = update["message"]
    text = msg.get("text", "")
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    name = msg["from"].get("first_name", "Player")
    user = get_user(user_id, name)

    if "emojis" not in user:
        user["emojis"] = []

    if text == "/store":
        store = "\n".join([f"{e} - {p} coins" for e, p in EMOJI_STORE.items()])
        send_message(chat_id, "*Emoji Store:*\n" + store, {"parse_mode": "Markdown"})

    elif text == "/collection":
        if user["emojis"]:
            send_message(chat_id, f"Your emojis: {' '.join(user['emojis'])}")
        else:
            send_message(chat_id, "You don’t own any emojis yet.")

    elif text.startswith("/give"):
        if "reply_to_message" not in msg:
            send_message(chat_id, "Reply to a user's message to gift emoji.")
            return {"ok": True}
        parts = text.split()
        if len(parts) != 2:
            send_message(chat_id, "Usage: /give emoji")
            return {"ok": True}
        emoji = parts[1]
        if emoji not in user["emojis"]:
            send_message(chat_id, "You don't own this emoji.")
            return {"ok": True}
        receiver_id = msg["reply_to_message"]["from"]["id"]
        receiver_name = msg["reply_to_message"]["from"].get("first_name", "Player")
        receiver = get_user(receiver_id, receiver_name)
        if "emojis" not in receiver:
            receiver["emojis"] = []
        receiver["emojis"].append(emoji)
        user["emojis"].remove(emoji)
        db.update(user, User.id == user_id)
        db.update(receiver, User.id == receiver_id)
        send_message(chat_id, f"Gave {emoji} to {receiver_name}!")

    return {"ok": True}

@app.route("/buy", methods=["POST"])
def buy_emoji():
    update = request.get_json()
    msg = update["message"]
    text = msg.get("text", "")
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    name = msg["from"].get("first_name", "Player")
    user = get_user(user_id, name)

    if "emojis" not in user:
        user["emojis"] = []

    parts = text.split()
    if len(parts) != 2:
        send_message(chat_id, "Usage: /buy <emoji>")
        return {"ok": True}

    emoji = parts[1]
    price = EMOJI_STORE.get(emoji)
    if not price:
        send_message(chat_id, "Emoji not found in store.")
        return {"ok": True}

    if emoji in user["emojis"]:
        send_message(chat_id, "You already own this emoji.")
        return {"ok": True}

    if user["coins"] < price:
        send_message(chat_id, "Not enough coins.")
        return {"ok": True}

    user["coins"] -= price
    user["emojis"].append(emoji)
    db.update(user, User.id == user_id)
    send_message(chat_id, f"You bought {emoji} for {price} coins!")

    return {"ok": True}
    
def send_message(chat_id, text, extra=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if extra:
        payload.update(extra)
    requests.post(f"{BASE}/sendMessage", json=payload)

@app.route("/", methods=["GET", "POST"])
def webhook_handler():
    if request.method == "POST":
        update = request.get_json()
        msg = update.get("message", {})
        text = msg.get("text", "")

        if text.startswith("/start"):
            return start_handler()
        elif text.startswith("/mine"):
            return mine_handler()
        elif text.startswith("/cashout"):
            return cashout_handler()
        elif text.startswith("/balance"):
            return balance_handler()
        elif text.startswith("/help"):
            return help_handler()
        elif text.startswith("/daily") or text.startswith("/weekly") or text.startswith("/leaderboard") or text.startswith("/gift"):
            return bonus_handler()
        elif text.startswith("/store") or text.startswith("/collection") or text.startswith("/give"):
            return emoji_handler()
        elif text.startswith("/buy"):
            return buy_emoji()
        elif text.startswith("/broadcast") or text.startswith("/resetdata") or text.startswith("/setbalance"):
            return admin_commands()
    return {"ok": True}
    
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
