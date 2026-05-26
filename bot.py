import json
import os
import time
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests

# ========== KONFIGURACIYA ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8825682305:AAFX8TNt5tTQI4JhnS757DHOITTDZ5UbW4I")
GROQ_KEYS = [
    os.environ.get("GROQ_KEY_1", "key1"),
    os.environ.get("GROQ_KEY_2", "key2"),
    os.environ.get("GROQ_KEY_3", "key3")
]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6122277497"))
GROQ_MODEL = "llama-3.3-70b-versatile"
MEMORY_FILE = "history_bot_memory.json"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
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
    [KeyboardButton("🎯 Викторина"), KeyboardButton("📚 Шпаргалка")],
    [KeyboardButton("📊 Статистика")]
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    user = get_user(uid)
    user["name"] = update.effective_user.first_name or ""
    user["username"] = update.effective_user.username or ""
    save_memory()
    await update.message.reply_text(
        "🏛️ *Istoricheskiy assistant*\n\n"
        "Privet! Ya pomogu tebe podgotovitsya k ekzamenu po istorii Rossii.\n\n"
        "🎯 *Viktorina* — ya zadayu vopros, ty otvechaesh, ya proveryayu.\n"
        "📚 *Shpargalka* — ty pishesh temu, ya dayu vyzhimku i daty.\n"
        "📊 *Statistika* — tvoy progress.\n"
        "🔄 /reset — sbrosit schyot viktoriny.\n\n"
        "Vyberi rezhim na klaviature 👇",
        parse_mode="Markdown", reply_markup=MAIN_KEYBOARD
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎯 *Viktorina* — nazhmi knopku, poluchi vopros, otvet tekstom.\n"
        "📚 *Shpargalka* — nazhmi knopku, napishi temu.\n"
        "📊 *Statistika* — posmotret progress.\n"
        "🔄 /reset — sbrosit schyot viktoriny.",
        parse_mode="Markdown"
    )

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    user = get_user(uid)
    user["quiz_recent"] = []
    user["quiz_cancelled"] = 0
    user["current_mode"] = None
    user["current_question"] = None
    save_memory()
    await update.message.reply_text("✅ Schyot viktoriny sbroshen.", reply_markup=MAIN_KEYBOARD)

async def reset_all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Tolko administrator.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Ukazhi ID: /reset_all 123456789")
        return
    uid = str(args[0])
    if uid in memory:
        del memory[uid]
        save_memory()
        await update.message.reply_text(f"✅ Statistika uchenika {uid} udalena.")
    else:
        await update.message.reply_text("❌ Uchenik ne nayden.")

async def user_stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Tolko administrator.")
        return
    users = list(memory.keys())
    if not users:
        await update.message.reply_text("Net uchenikov.")
        return
    page = int(context.args[0]) - 1 if context.args else 0
    per_page = 5
    page_users = users[page*per_page:(page+1)*per_page]
    msg = f"📊 *Statistika uchenikov* (str. {page+1}/{(len(users)-1)//per_page+1})\n\n"
    for uid in page_users:
        u = memory[uid]
        recent = u.get("quiz_recent", [])
        correct = sum(1 for r in recent if r.get("correct"))
        wrong = len(recent) - correct
        themes = len(set(t["theme"] for t in u.get("cheat_themes", [])))
        msg += f"👤 {u.get('name','?')} (@{u.get('username','?')})\nID: {uid}\n"
        msg += f"Viktoriny: {u.get('quiz_total',0)} (✅{correct} ❌{wrong})\nShpargalki: {themes} tem\n\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    user = get_user(uid)
    text = update.message.text
    
    if text == "🎯 Викторина":
        if user["current_mode"] == "quiz" and user["current_question"]:
            user["quiz_cancelled"] += 1
        user["current_mode"] = "quiz"
        user["mode_history"].append({"mode": "quiz", "time": datetime.now().isoformat()})
        q = ask_groq([
            {"role": "system", "content": "Ty — ekzamenator po istorii Rossii (8 klass). Pr dumay ODIN vopros s konkretnym otvetom. Pishi tolko vopros."},
            {"role": "user", "content": "Zaday vopros po istorii Rossii."}
        ])
        if q:
            user["current_question"] = q
            save_memory()
            await update.message.reply_text(f"🎯 Vopros:\n\n{q}\n\nNapishi svoy otvet:")
        else:
            await update.message.reply_text("❌ Ne udalos sgenerirovat vopros.")
    
    elif text == "📚 Шпаргалка":
        if user["current_mode"] == "quiz" and user["current_question"]:
            user["quiz_cancelled"] += 1
        user["current_mode"] = "cheatsheet"
        user["current_question"] = None
        user["mode_history"].append({"mode": "cheatsheet", "time": datetime.now().isoformat()})
        save_memory()
        await update.message.reply_text("📚 Napishi temu, naprimer: «Pravlenie Petra I»")
    
    elif text == "📊 Статистика":
        await show_user_stats(update, user)

async def show_user_stats(update, user):
    recent = user.get("quiz_recent", [])
    correct = sum(1 for r in recent if r.get("correct"))
    wrong = len(recent) - correct
    themes = [t["theme"] for t in user.get("cheat_themes", [])]
    unique = len(set(themes))
    last = themes[-15:] if len(themes) > 15 else themes
    msg = f"📊 *Tvoya statistika*\n\n🎯 Viktoriny: {user.get('quiz_total',0)}\n✅ Pravilnyh: {correct}\n❌ Nepravilnyh: {wrong}\n\n📚 Shpargalki (tem): {unique}\n"
    if last:
        msg += "Temy:\n" + "\n".join(f"• {t}" for t in last)
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    user = get_user(uid)
    text = update.message.text.strip()
    if text in ["🎯 Викторина", "📚 Шпаргалка", "📊 Статистика"]:
        return
    
    if user["current_mode"] == "quiz" and user["current_question"]:
        result = ask_groq([
            {"role": "system", "content": "Prover otvet. Verno — «Verno!» + poyasnenie. Neverno — «Neverno. Pravilny otvet: ...» + poyasnenie."},
            {"role": "user", "content": f"Vopros: {user['current_question']}\nOtvet: {text}"}
        ])
        if result:
            is_correct = result.lower().startswith("verno")
            user["quiz_recent"].append({"q": user["current_question"], "a": text, "correct": is_correct, "time": datetime.now().isoformat()})
            if len(user["quiz_recent"]) > 20:
                user["quiz_recent"] = user["quiz_recent"][-20:]
            user["quiz_total"] += 1
            user["current_question"] = None
            save_memory()
            await update.message.reply_text(result)
            await update.message.reply_text("Nazhmi 🎯 Viktorina dlya novogo voprosa.", reply_markup=MAIN_KEYBOARD)
        else:
            await update.message.reply_text("❌ Ne udalos proverit otvet.")
    
    elif user["current_mode"] == "cheatsheet":
        result = ask_groq([
            {"role": "system", "content": "Ty — repetitor po istorii. Day vyzhimku 3-5 predlozheniy i 2-3 klyuchevye daty."},
            {"role": "user", "content": f"Tema: {text}"}
        ])
        if result:
            user["cheat_themes"].append({"theme": text, "time": datetime.now().isoformat()})
            if len(user["cheat_themes"]) > 50:
                user["cheat_themes"] = user["cheat_themes"][-50:]
            save_memory()
            await update.message.reply_text(result)
            await update.message.reply_text("Napishi eshchyo temu ili nazhmi 🎯 Viktorina.", reply_markup=MAIN_KEYBOARD)
        else:
            await update.message.reply_text("❌ Ne udalos sgenerirovat shpargalku.")
    else:
        await update.message.reply_text("Snachala vyberi rezhim: 🎯 Viktorina ili 📚 Shpargalka.", reply_markup=MAIN_KEYBOARD)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CommandHandler("reset_all", reset_all_cmd))
    app.add_handler(CommandHandler("user_stats", user_stats_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mode))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))
    print("🏛️ Istoricheskiy assistant zapushchen!")
    app.run_polling()

if __name__ == "__main__":
    main()
