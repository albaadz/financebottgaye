import os
import re
import sqlite3
from datetime import datetime
import telebot
from telebot import types

# ================= НАСТРОЙКИ =================
# Бот берёт токен и ID из настроек хостинга (или из кавычек, если не заданы переменные)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8873587943:AAH5vwpWWbn212_sTgnXoVK9DtFdLBoL1FM")
ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID", "0"))  # Твой числовой Telegram ID

bot = telebot.TeleBot(BOT_TOKEN)

# ================= БАЗА ДАННЫХ =================
def init_db():
    with sqlite3.connect("finances.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                item TEXT,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

# ================= СЛОВАРЬ КАТЕГОРИЙ =================
CATEGORIES = {
    "☕ Кафе и фастфуд": [
        "кофе", "капучино", "латте", "раф", "бургер", "пицца", "суши", "роллы", 
        "шаурма", "шаверма", "додо", "кфс", "kfc", "вкусно и точка", "мак", 
        "ресторан", "кафе", "бар", "столовая", "обед", "ужин", "кальян", "доставка"
    ],
    "🍏 Продукты": [
        "хлеб", "молоко", "сыр", "яйца", "мясо", "курица", "рыба", "овощи", 
        "фрукты", "яблоки", "бананы", "магнит", "пятерочка", "пятерка", "лента", 
        "вкусвилл", "перекресток", "ашан", "спар", "продукты", "чипсы", "шоколад"
    ],
    "🚖 Транспорт": [
        "маршрутка", "автобус", "метро", "проезд", "проездной", "такси", "яндекс", 
        "убер", "uber", "бензин", "газ", "заправка", "лукойл", "газпром", 
        "каршеринг", "парковка", "электричка", "поезд", "самолет", "билет"
    ],
    "🛍 Покупки и дом": [
        "одежда", "кроссовки", "обувь", "куртка", "футболка", "ozon", "озон", 
        "вб", "wildberries", "али", "aliexpress", "техника", "бытовая", "химия", 
        "мыло", "порошок", "уют", "посуда", "лампа"
    ],
    "💊 Здоровье": [
        "аптека", "таблетки", "лекарства", "врач", "стоматолог", "анализы", 
        "витамины", "зал", "абонемент", "фитнес", "линзы", "массаж"
    ],
    "🎮 Развлечения": [
        "кино", "фильм", "билеты", "игры", "steam", "стим", "подписка", 
        "музыка", "яндекс плюс", "спотифай", "боулинг", "квест", "книга"
    ],
    "📱 Связь и счета": [
        "интернет", "связь", "телефон", "мтс", "билайн", "мегафон", "т2", 
        "теле2", "жкх", "аренда", "квартира", "свет", "вода"
    ]
}

def detect_category(item_name: str) -> str:
    item_lower = item_name.lower().strip()
    for cat, keywords in CATEGORIES.items():
        for word in keywords:
            if word in item_lower:
                return cat
    return "📦 Другое"

def is_authorized(obj) -> bool:
    if ALLOWED_USER_ID == 0:
        return True
    return obj.from_user.id == ALLOWED_USER_ID

def get_main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 Сегодня", "📅 Этот месяц")
    kb.row("📋 Последние траты", "❓ Справка")
    return kb

def get_action_keyboard(trans_id: int):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✏️ Сменить категорию", callback_data=f"editcat_{trans_id}"),
        types.InlineKeyboardButton("❌ Отменить", callback_data=f"del_{trans_id}")
    )
    return kb

def get_categories_keyboard(trans_id: int):
    kb = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton(cat, callback_data=f"setcat_{trans_id}_{i}")
        for i, cat in enumerate(CATEGORIES.keys())
    ]
    buttons.append(types.InlineKeyboardButton("📦 Другое", callback_data=f"setcat_{trans_id}_other"))
    kb.add(*buttons)
    return kb

# ================= ОБРАБОТЧИКИ =================
@bot.message_handler(commands=['start'])
def handle_start(message):
    if not is_authorized(message): return
    bot.send_message(
        message.chat.id,
        "👋 **CoinKeeper готов к учету расходов!**\n\n"
        "Отправляй траты: `кофе 300` или `маршрутка 40`.\n"
        "Категория определится автоматически.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(commands=['myid'])
def handle_myid(message):
    bot.reply_to(message, f"Твой Telegram ID: `{message.from_user.id}`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "❓ Справка")
def handle_help(message):
    if not is_authorized(message): return
    bot.send_message(
        message.chat.id,
        "📌 **Примеры сообщений:**\n"
        "• `кофе 300`\n"
        "• `маршрутка 40`\n"
        "• `бургер 350`\n"
        "• `пятерочка 1240`\n\n"
        "Под каждой записью можно сменить категорию или отменить трату.",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "📊 Сегодня")
def handle_today(message):
    if not is_authorized(message): return
    today_str = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect("finances.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, SUM(amount) 
            FROM transactions 
            WHERE user_id = ? AND date(created_at) = ? 
            GROUP BY category
            ORDER BY SUM(amount) DESC
        """, (message.from_user.id, today_str))
        rows = cursor.fetchall()

    if not rows:
        bot.send_message(message.chat.id, "За сегодня трат ещё не было 🎉")
        return

    total = sum(r[1] for r in rows)
    text = f"📊 **Траты за сегодня:** {total:,.2f} ₽\n\n".replace(",", " ")
    for cat, amt in rows:
        pct = (amt / total) * 100
        text += f"{cat}: **{amt:,.2f} ₽** ({pct:.1f}%)\n".replace(",", " ")
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📅 Этот месяц")
def handle_month(message):
    if not is_authorized(message): return
    month_str = datetime.now().strftime("%Y-%m")
    with sqlite3.connect("finances.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, SUM(amount) 
            FROM transactions 
            WHERE user_id = ? AND strftime('%Y-%m', created_at) = ? 
            GROUP BY category 
            ORDER BY SUM(amount) DESC
        """, (message.from_user.id, month_str))
        rows = cursor.fetchall()

    if not rows:
        bot.send_message(message.chat.id, "В этом месяце трат пока нет.")
        return

    total = sum(r[1] for r in rows)
    text = f"📅 **Траты за текущий месяц:** {total:,.2f} ₽\n\n".replace(",", " ")
    for cat, amt in rows:
        pct = (amt / total) * 100
        bars = int(pct // 10)
        progress = "▰" * bars + "▱" * (10 - bars)
        text += f"{cat}\n{progress} {amt:,.2f} ₽ ({pct:.1f}%)\n\n".replace(",", " ")
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📋 Последние траты")
def handle_history(message):
    if not is_authorized(message): return
    with sqlite3.connect("finances.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, item, amount, category, datetime(created_at, 'localtime')
            FROM transactions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 7
        """, (message.from_user.id,))
        rows = cursor.fetchall()

    if not rows:
        bot.send_message(message.chat.id, "История трат пуста.")
        return

    text = "📋 **Последние операции:**\n\n"
    for row in rows:
        _, item, amt, cat, date_str = row
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").strftime("%d.%m %H:%M")
        text += f"• `{dt}` — **{amt:,.2f} ₽** ({item}) | _{cat}_\n".replace(",", " ")
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(content_types=['text'])
def handle_transaction(message):
    if not is_authorized(message): return
    text = message.text.strip().replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:р|руб)?", text)
    if not match:
        bot.reply_to(message, "Укажи название и сумму, например: `кофе 300` или `маршрутка 40`")
        return

    amount = float(match.group(1))
    item = re.sub(r"(\d+(?:\.\d+)?)\s*(?:р|руб)?", "", text, count=1).strip()
    if not item:
        item = "Расход"

    category = detect_category(item)

    with sqlite3.connect("finances.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, item, category)
            VALUES (?, ?, ?, ?)
        """, (message.from_user.id, amount, item.capitalize(), category))
        conn.commit()
        trans_id = cursor.lastrowid

    bot.reply_to(
        message,
        f"✅ **Записано:** {amount:,.2f} ₽\n"
        f"📌 **Товар:** {item.capitalize()}\n"
        f"📂 **Категория:** {category}".replace(",", " "),
        parse_mode="Markdown",
        reply_markup=get_action_keyboard(trans_id)
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if not is_authorized(call):
        bot.answer_callback_query(call.id, "Доступ ограничен.")
        return

    data = call.data
    if data.startswith("del_"):
        trans_id = int(data.split("_")[1])
        with sqlite3.connect("finances.db") as conn:
            conn.cursor().execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (trans_id, call.from_user.id))
            conn.commit()
        bot.edit_message_text("❌ Запись отменена.", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Удалено")

    elif data.startswith("editcat_"):
        trans_id = int(data.split("_")[1])
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_categories_keyboard(trans_id))
        bot.answer_callback_query(call.id)

    elif data.startswith("setcat_"):
        parts = data.split("_")
        trans_id = int(parts[1])
        cat_idx = parts[2]
        cat_keys = list(CATEGORIES.keys())
        new_cat = "📦 Другое" if cat_idx == "other" else cat_keys[int(cat_idx)]

        with sqlite3.connect("finances.db") as conn:
            conn.cursor().execute("UPDATE transactions SET category = ? WHERE id = ? AND user_id = ?", (new_cat, trans_id, call.from_user.id))
            conn.commit()

        bot.edit_message_text(
            f"{call.message.text.split('📂')[0]}📂 **Категория изменена на:** {new_cat}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_action_keyboard(trans_id)
        )
        bot.answer_callback_query(call.id, f"Категория: {new_cat}")

if __name__ == "__main__":
    print("Бот CoinKeeper запущен...")
    bot.infinity_polling(skip_pending=True)
