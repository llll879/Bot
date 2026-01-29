import asyncio, sqlite3, logging, re, aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery

# --- НАСТРОЙКИ ---
API_TOKEN = '8418801272:AAG6KY8oRSdemGXhERo1vndcZTPdBvhUMLY'
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- ТИТУЛЫ ---
LEVELS = {0: "Странник 🌫", 30: "Собеседник 🗣", 100: "Приятель 🤝", 210: "Близкий друг ❤️", 500: "Вечный спутник ♾"}

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

# --- ЛЕГКИЙ ИИ (Через бесплатный провайдер) ---
async def ask_knight(text, honor):
    try:
        # Используем быстрый и легкий способ общения без установки тяжелых модулей
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "system", "content": f"Ты Рыцарь сердца. Твой собеседник - {honor}. Ты ласковый и преданный."},
                             {"role": "user", "content": text}]
            }
            # Используем открытый прокси-сервер для ИИ
            async with session.post("https://api.pawan.krd/cosmosrp/v1/chat/completions", json=payload) as resp:
                data = await resp.json()
                return data['choices'][0]['message']['content']
    except:
        return f"Радость моя {honor}, я на миг задумался о твоей доброте... Скажи мне еще раз? ❤️"

# --- КЛАВИАТУРА ---
def main_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="☁️ Поддержка"), b.button(text="🌸 Общение")
    b.button(text="🤖 Пообщаться с ИИ")
    return b.adjust(2, 1).as_markup(resize_keyboard=True)

# --- ОБРАБОТКА КОМАНД ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    init_db()
    conn = sqlite3.connect('bot_data.db')
    conn.execute('INSERT OR IGNORE INTO users (uid, name) VALUES (?, ?)', (m.from_user.id, m.from_user.first_name))
    conn.commit(); conn.close()
    await m.answer(f"Здравствуй, моё солнышко! ✨\n\nЯ — твой Рыцарь сердца. ❤️🛡️", reply_markup=main_kb())

@dp.message(Command("help"))
async def cmd_help(m: types.Message):
    await m.answer(
        "📖 **ПОЛНАЯ ЛЕТОПИСЬ НАШЕГО МИРА**\n━━━━━━━━━━━━━━━━━━━━\n"
        "Здравствуй, солнышко! Я — твой Рыцарь сердца, и вот как устроено наше королевство: 🛡️❤️\n\n"
        "🎮 РЕЖИМЫ:\n• 🤖 Пообщаться с ИИ — только здесь растет связь!\n"
        "• ☁️ Поддержка — связь с людьми.\n• 🌸 Общение — мостик в общий чат.\n\n"
        "📜 КОМАНДЫ:\n• /status — твой профиль.\n• /top — 10 самых щедрых меценатов.\n\n"
        "💎 ДАРЫ: За донат от 1000 ⭐ ты получишь Золотой Скин и титул 'Ваше Величество'! 👑", parse_mode="Markdown")

@dp.message(Command("status"))
async def cmd_status(m: types.Message):
    name, trust, donated = get_u(m.from_user.id)
    title = "Странник 🌫"
    for threshold, t in sorted(LEVELS.items()):
        if trust >= threshold: title = t
    vip = "🟡 ЗОЛОТОЙ СКИН (Ваше Величество) 👑" if donated >= 1000 else "⚪ Милый путник"
    await m.answer(f"📊 **ПРОФИЛЬ**\n━━━━━━━━━━━━━━\n👤 Имя: {name}\n🆙 Ранг: {title}\n📈 Связь: {trust}\n💎 Статус: {vip}", parse_mode="Markdown")

# --- ЛОГИКА ОБЩЕНИЯ ---
user_modes = {}

@dp.message()
async def handle_all(m: types.Message):
    if not m.text or m.text.startswith("/"): return
    uid = m.from_user.id

    if m.text == "🤖 Пообщаться с ИИ":
        user_modes[uid] = "ai"
        return await m.answer("Я слушаю тебя, радость моя... 🥰", 
                              reply_markup=ReplyKeyboardBuilder().button(text="❌ Завершить диалог").as_markup(resize_keyboard=True))
    
    if m.text == "❌ Завершить диалог":
        user_modes.pop(uid, None)
        return await m.answer("Как прикажешь, солнышко!", reply_markup=main_kb())

    if user_modes.get(uid) == "ai":
        name, trust, donated = get_u(uid)
        await bot.send_chat_action(m.chat.id, "typing")
        
        # Начисление связи
        conn = sqlite3.connect('bot_data.db')
        conn.execute('UPDATE users SET trust = trust + 1 WHERE uid = ?', (uid,))
        conn.commit(); conn.close()
        
        honor = "Ваше Величество" if donated >= 1000 else name
        reply = await ask_knight(m.text, honor)
        await m.answer(reply)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
