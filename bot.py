import json
import os
import time
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram.utils.request import Request
import requests

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8825682305:AAFX8TNt5tTQI4JhnS757DHOITTDZ5UbW4I")
GROQ_KEYS = [
    os.environ.get("GROQ_KEY_1", "ключ1"),
    os.environ.get("GROQ_KEY_2", "ключ2"),
    os.environ.get("GROQ_KEY_3", "ключ3")
]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6122277497"))
GROQ_MODEL = "llama-3.3-70b-versatile"
MEMORY_FILE = "history_bot_memory.json"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ПРОКСИ (для России)
PROXY_URL = os.environ.get("PROXY_URL", "socks5://127.0.0.1:9150")  # Замени если нужно
USE_PROXY = os.environ.get("USE_PROXY", "true").lower() == "true"
# ====================================

key_index = 0

def get_headers():
    return {"Authorization": f"Bearer {GROQ_KEYS[key_index]}", "Content-Type": "application/json"}

def switch_key():
    global key_index
    key_index = (key_index + 1) % len(GROQ_KEYS)

memory = {}
def load_memory():
    global memory
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            memory = json.load(f)
    except:
        memory = {}

def save_memory():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

load_memory()

def get_user(uid):
    uid = str(uid)
    if uid not in memory:
        memory[uid] = {
            "name": "", "username": "", "quiz_total": 0, "quiz_recent": [],
            "cheat_themes": [], "mode_history": [], "current_mode": None,
            "current_question": None, "quiz_cancelled": 0
        }
        save_memory()
    return memory[uid]

MAIN_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("?? Викторина"), KeyboardButton("?? Шпаргалка")],
    [KeyboardButton("?? Статистика")]
], resize_keyboard=True)

def ask_groq(messages):
    global key_index
    for _ in range(len(GROQ_KEYS)):
        try:
            r = requests.post(GROQ_URL, headers=get_headers(), json={
                "model": GROQ_MODEL, "messages": messages,
                "temperature": 0.7, "max_tokens": 300
            }, timeout=15)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            elif r.status_code in (429, 401):
                switch_key()
        except:
            switch_key()
    return None

def start(update: Update, context: CallbackContext):
    uid = str(update.effective_user.id)
    user = get_user(uid)
    user["name"] = update.effective_user.first_name or ""
    user["username"] = update.effective_user.username or ""
    save_memory()
    update.message.reply_text(
        "??? *Исторический ассистент*\n\n"
        "Привет! Я помогу тебе подготовиться к экзамену по истории России.\n\n"
        "?? *Викторина* — я задаю вопрос, ты отвечаешь, я проверяю.\n"
        "?? *Шпаргалка* — ты пишешь тему, я даю выжимку и даты.\n"
        "?? *Статистика* — твой прогресс.\n"
        "?? /reset — сбросить счёт викторины.\n\n"
        "Выбери режим на клавиатуре ??",
        parse_mode="Markdown", reply_markup=MAIN_KEYBOARD
    )

def help_cmd(update: Update, context: CallbackContext):
    update.message.reply_text(
        "?? *Викторина* — нажми кнопку, получи вопрос, ответь текстом.\n"
        "?? *Шпаргалка* — нажми кнопку, напиши тему.\n"
        "?? *Статистика* — посмотреть прогресс.\n"
        "?? /reset — сбросить счёт викторины.\n\n"
        "По вопросам — к учителю истории.",
        parse_mode="Markdown"
    )

def reset_cmd(update: Update, context: CallbackContext):
    uid = str(update.effective_user.id)
    user = get_user(uid)
    user["quiz_recent"] = []
    user["quiz_cancelled"] = 0
    user["current_mode"] = None
    user["current_question"] = None
    save_memory()
    update.message.reply_text("? Счёт викторины сброшен.", reply_markup=MAIN_KEYBOARD)

def reset_all_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("? Только администратор.")
        return
    args = context.args
    if not args:
        update.message.reply_text("Укажи ID: /reset_all 123456789")
        return
    uid = str(args[0])
    if uid in memory:
        del memory[uid]
        save_memory()
        update.message.reply_text(f"? Статистика ученика {uid} удалена.")
    else:
        update.message.reply_text("? Ученик не найден.")

def user_stats_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("? Только администратор.")
        return
    users = list(memory.keys())
    if not users:
        update.message.reply_text("Нет учеников.")
        return
    page = int(context.args[0]) - 1 if context.args else 0
    per_page = 5
    page_users = users[page*per_page:(page+1)*per_page]
    msg = f"?? *Статистика учеников* (стр. {page+1}/{(len(users)-1)//per_page+1})\n\n"
    for uid in page_users:
        u = memory[uid]
        recent = u.get("quiz_recent", [])
        correct = sum(1 for r in recent if r.get("correct"))
        wrong = len(recent) - correct
        themes = len(set(t["theme"] for t in u.get("cheat_themes", [])))
        msg += f"?? {u.get('name','?')} (@{u.get('username','?')})\nID: {uid}\n"
        msg += f"Викторины: {u.get('quiz_total',0)} (?{correct} ?{wrong})\nШпаргалки: {themes} тем\n\n"
    update.message.reply_text(msg, parse_mode="Markdown")

def handle_mode(update: Update, context: CallbackContext):
    uid = str(update.effective_user.id)
    user = get_user(uid)
    text = update.message.text
    
    if text == "?? Викторина":
        if user["current_mode"] == "quiz" and user["current_question"]:
            user["quiz_cancelled"] += 1
        user["current_mode"] = "quiz"
        user["mode_history"].append({"mode": "quiz", "time": datetime.now().isoformat()})
        q = ask_groq([
            {"role": "system", "content": "Ты — экзаменатор по истории России (8 класс). Придумай ОДИН вопрос с конкретным ответом. Пиши только вопрос."},
            {"role": "user", "content": "Задай вопрос по истории России."}
        ])
        if q:
            user["current_question"] = q
            save_memory()
            update.message.reply_text(f"?? Вопрос:\n\n{q}\n\nНапиши свой ответ:")
        else:
            update.message.reply_text("? Не удалось сгенерировать вопрос.")
    
    elif text == "?? Шпаргалка":
        if user["current_mode"] == "quiz" and user["current_question"]:
            user["quiz_cancelled"] += 1
        user["current_mode"] = "cheatsheet"
        user["current_question"] = None
        user["mode_history"].append({"mode": "cheatsheet", "time": datetime.now().isoformat()})
        save_memory()
        update.message.reply_text("?? Напиши тему, например: «Правление Петра I»")
    
    elif text == "?? Статистика":
        show_user_stats(update, user)

def show_user_stats(update, user):
    recent = user.get("quiz_recent", [])
    correct = sum(1 for r in recent if r.get("correct"))
    wrong = len(recent) - correct
    themes = [t["theme"] for t in user.get("cheat_themes", [])]
    unique = len(set(themes))
    last = themes[-15:] if len(themes) > 15 else themes
    msg = f"?? *Твоя статистика*\n\n?? Викторины: {user.get('quiz_total',0)}\n? Правильных: {correct}\n? Неправильных: {wrong}\n\n?? Шпаргалки (тем): {unique}\n"
    if last:
        msg += "Темы:\n" + "\n".join(f"• {t}" for t in last)
    update.message.reply_text(msg, parse_mode="Markdown")

def handle_answer(update: Update, context: CallbackContext):
    uid = str(update.effective_user.id)
    user = get_user(uid)
    text = update.message.text.strip()
    if text in ["?? Викторина", "?? Шпаргалка", "?? Статистика"]:
        return
    
    if user["current_mode"] == "quiz" and user["current_question"]:
        result = ask_groq([
            {"role": "system", "content": "Проверь ответ. Верно — «Верно!» + пояснение. Неверно — «Неверно. Правильный ответ: ...» + пояснение."},
            {"role": "user", "content": f"Вопрос: {user['current_question']}\nОтвет: {text}"}
        ])
        if result:
            is_correct = result.lower().startswith("верно")
            user["quiz_recent"].append({"q": user["current_question"], "a": text, "correct": is_correct, "time": datetime.now().isoformat()})
            if len(user["quiz_recent"]) > 20:
                user["quiz_recent"] = user["quiz_recent"][-20:]
            user["quiz_total"] += 1
            user["current_question"] = None
            save_memory()
            update.message.reply_text(result)
            update.message.reply_text("Нажми ?? Викторина для нового вопроса.", reply_markup=MAIN_KEYBOARD)
        else:
            update.message.reply_text("? Не удалось проверить ответ.")
    
    elif user["current_mode"] == "cheatsheet":
        result = ask_groq([
            {"role": "system", "content": "Ты — репетитор по истории. Дай выжимку 3-5 предложений и 2-3 ключевые даты."},
            {"role": "user", "content": f"Тема: {text}"}
        ])
        if result:
            user["cheat_themes"].append({"theme": text, "time": datetime.now().isoformat()})
            if len(user["cheat_themes"]) > 50:
                user["cheat_themes"] = user["cheat_themes"][-50:]
            save_memory()
            update.message.reply_text(result)
            update.message.reply_text("Напиши ещё тему или нажми ?? Викторина.", reply_markup=MAIN_KEYBOARD)
        else:
            update.message.reply_text("? Не удалось сгенерировать шпаргалку.")
    else:
        update.message.reply_text("Сначала выбери режим: ?? Викторина или ?? Шпаргалка.", reply_markup=MAIN_KEYBOARD)

def main():
    # Настройка прокси
    if USE_PROXY:
        request_kwargs = {'proxy_url': PROXY_URL}
        print(f"?? Использую прокси: {PROXY_URL}")
    else:
        request_kwargs = {}
        print("?? Прокси отключён")
    
    updater = Updater(BOT_TOKEN, request_kwargs=request_kwargs)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_cmd))
    dp.add_handler(CommandHandler("reset", reset_cmd))
    dp.add_handler(CommandHandler("reset_all", reset_all_cmd))
    dp.add_handler(CommandHandler("user_stats", user_stats_cmd))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_mode))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_answer))
    print("??? Исторический ассистент запущен!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()