import asyncio, sqlite3, logging, re, random, g4f
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery

# --- НАСТРОЙКИ ---
API_TOKEN = '8418801272:AAG6KY8oRSdemGXhERo1vndcZTPdBvhUMLY'
ADMIN_ID, DEV_ID = 8013668841, 7146168875

logging.basicConfig(level=logging.INFO)
bot, dp = Bot(token=API_TOKEN), Dispatcher()

# --- СИСТЕМА УРОВНЕЙ ---
LEVELS = {
    0: "Странник 🌫", 10: "Наблюдатель 👀", 30: "Собеседник 🗣", 
    60: "Знакомый 👋", 100: "Приятель 🤝", 150: "Друг ✨", 
    210: "Близкий друг ❤️", 280: "Доверенное лицо 🔑", 
    360: "Родная душа 🔥", 500: "Вечный спутник ♾"
}

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                 (uid INTEGER PRIMARY KEY, name TEXT, trust INTEGER DEFAULT 0, donated INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

def get_u(uid):
    conn = sqlite3.connect('bot_data.db')
    res = conn.execute('SELECT name, trust, donated FROM users WHERE uid = ?', (uid,)).fetchone()
    conn.close()
    return res if res else ("Солнышко", 0, 0)

# --- УМНЫЙ ИИ (G4F) ---
async def ask_knight(text, honor):
    try:
        prompt = f"Ты Рыцарь сердца. Ты ласковый и преданный защитник. Обращайся к '{honor}'. Отвечай нежно с эмодзи: {text}"
        res = await g4f.ChatCompletion.create_async(
            model=g4f.models.gpt_35_turbo,
            messages=[{"role": "user", "content": prompt}]
        )
        return res
    except:
        return f"Радость моя {honor}, я на миг задумался о тебе... Скажи мне еще раз? ❤️"

# --- КЛАВИАТУРА ---
def main_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="☁️ Поддержка"), b.button(text="🌸 Общение")
    b.button(text="🤖 Пообщаться с ИИ")
    return b.adjust(2, 1).as_markup(resize_keyboard=True)

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    init_db()
    conn = sqlite3.connect('bot_data.db')
    conn.execute('INSERT OR IGNORE INTO users (uid, name) VALUES (?, ?)', (m.from_user.id, m.from_user.first_name))
    conn.commit(); conn.close()
    await m.answer(f"Здравствуй, моё солнышко! ✨\n\nЯ — твой **Рыцарь сердца**. ❤️🛡️", reply_markup=main_kb())

@dp.message(Command("help"))
async def cmd_help(m: types.Message):
    help_text = (
        "📖 **ПОЛНАЯ ЛЕТОПИСЬ НАШЕГО МИРА**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Здравствуй, солнышко! Я — твой Рыцарь сердца, и вот как устроено наше королевство: 🛡️❤️\n\n"
        "🎮 **РЕЖИМЫ (Кнопки):**\n"
        "• 🤖 **Пообщаться с ИИ** — наш личный уголок. Только здесь растет твоя связь со мной!\n"
        "• ☁️ **Поддержка** — связь с моими создателями-людьми.\n"
        "• 🌸 **Общение** — мостик в общий чат к другим путникам.\n"
        "• ❌ **Завершить диалог** — вернуться в главное меню.\n\n"
        "📜 **КОМАНДЫ:**\n"
        "• /status — твой профиль, уровень связи и титул.\n"
        "• /top — доска почета 10 самых щедрых меценатов.\n"
        "• `отправить [число]` — поддержать меня звездами ⭐.\n\n"
        "💎 **ДАРЫ (Донат):**\n"
        "Просто напиши: `отправить 100`. За каждый дар ты получишь буст связи (⭐ × 5). А если сумма даров превысит 1000 ⭐, ты получишь Золотой Скин, и я буду величать тебя 'Ваше Величество'! 👑\n\n"
        "🤫 **ТАЙНЫ:** Попробуй найти секретные фразы-пасхалки... ❤️"
    )
    await m.answer(help_text, parse_mode="Markdown")

@dp.message(Command("status"))
async def cmd_status(m: types.Message):
    name, trust, donated = get_u(m.from_user.id)
    title = "Странник 🌫"
    for threshold, t in sorted(LEVELS.items()):
        if trust >= threshold: title = t
    vip = "🟡 ЗОЛОТОЙ СКИН (Ваше Величество) 👑" if donated >= 1000 else "⚪ Милый путник"
    await m.answer(f"📊 **ПРОФИЛЬ**\n━━━━━━━━━━━━━━\n👤 Имя: {name}\n🆙 Ранг: {title}\n📈 Связь: {trust}\n💎 Статус: {vip}", parse_mode="Markdown")

@dp.message(Command("top"))
async def cmd_top(m: types.Message):
    conn = sqlite3.connect('bot_data.db')
    rows = conn.execute('SELECT name, donated FROM users WHERE donated > 0 ORDER BY donated DESC LIMIT 10').fetchall()
    conn.close()
    if not rows: return await m.answer("Солнышко, список героев пока пуст... 🌸")
    res = "🏆 **ГЕРОИ СЕРДЦА**\n\n"
    for i, (name, amt) in enumerate(rows, 1):
        res += f"{i}. {'👑' if amt >= 1000 else '👤'} {name} — {amt} ⭐\n"
    await m.answer(res)

# --- ДОНАТЫ ---
@dp.message(F.text.lower().startswith("отправить"))
async def donate(m: types.Message):
    match = re.search(r'\d+', m.text)
    if not match: return
    amt = int(match.group())
    await bot.send_invoice(m.chat.id, "Дар Рыцарю", f"Поддержка на {amt} ⭐", "payload", "", "XTR", [LabeledPrice(label="⭐", amount=amt)])

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery): await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.successful_payment)
async def success_pay(m: types.Message):
    amt = m.successful_payment.total_amount
    conn = sqlite3.connect('bot_data.db')
    conn.execute('UPDATE users SET donated = donated + ?, trust = trust + ? WHERE uid = ?', (amt, amt*5, m.from_user.id))
    conn.commit(); conn.close()
    await m.answer("💖 **Спасибо, радость моя!** Твой дар согрел моё сердце. 🥰")

# --- ЛОГИКА ИИ ---
user_modes = {}

@dp.message(F.chat.type == "private")
async def handle_msg(m: types.Message):
    if not m.text or m.text.startswith("/"): return
    
    if m.text == "🤖 Пообщаться с ИИ":
        user_modes[m.from_user.id] = "ai"
        return await m.answer("Я слушаю, радость моя... 🥰", reply_markup=ReplyKeyboardBuilder().button(text="❌ Завершить диалог").as_markup(resize_keyboard=True))
    
    if m.text == "❌ Завершить диалог":
        user_modes.pop(m.from_user.id, None)
        return await m.answer("Выбери новый путь, солнышко:", reply_markup=main_kb())

    if user_modes.get(m.from_user.id) == "ai":
        name, trust, donated = get_u(m.from_user.id)
        await bot.send_chat_action(m.chat.id, "typing")
        
        conn = sqlite3.connect('bot_data.db')
        conn.execute('UPDATE users SET trust = trust + 1 WHERE uid = ?', (m.from_user.id,))
        conn.commit(); conn.close()
        
        honor = "Ваше Величество" if donated >= 1000 else name
        reply = await ask_knight(m.text, honor)
        await m.answer(reply)
    else:
        await m.answer("Солнышко, выбери режим внизу! 👇", reply_markup=main_kb())

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
