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

LEVELS = {0: "Странник 🌫", 30: "Собеседник 🗣", 100: "Приятель 🤝", 210: "Близкий друг ❤️", 500: "Вечный спутник ♾"}

def init_db():
    conn = sqlite3.connect('bot_data.db')
    conn.execute('CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, name TEXT, trust INTEGER DEFAULT 0, donated INTEGER DEFAULT 0)')
    conn.commit(); conn.close()

def get_u(uid):
    conn = sqlite3.connect('bot_data.db')
    res = conn.execute('SELECT name, trust, donated FROM users WHERE uid = ?', (uid,)).fetchone()
    conn.close()
    return res if res else ("Солнышко", 0, 0)

async def ask_knight(text, honor):
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"model": "gpt-3.5-turbo", "messages": [{"role": "system", "content": f"Ты Рыцарь сердца для {honor}."}, {"role": "user", "content": text}]}
            async with session.post("https://api.pawan.krd/cosmosrp/v1/chat/completions", json=payload, timeout=10) as resp:
                data = await resp.json()
                return data['choices'][0]['message']['content']
    except: return f"Радость моя {honor}, я задумался о тебе... ❤️"

def main_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="☁️ Поддержка"), b.button(text="🌸 Общение")
    b.button(text="🤖 Пообщаться с ИИ")
    return b.adjust(2, 1).as_markup(resize_keyboard=True)

@dp.message(Command("start"))
async def st(m: types.Message):
    init_db()
    conn = sqlite3.connect('bot_data.db')
    conn.execute('INSERT OR IGNORE INTO users (uid, name) VALUES (?, ?)', (m.from_user.id, m.from_user.first_name))
    conn.commit(); conn.close()
    await m.answer(f"Здравствуй, моё солнышко! ✨", reply_markup=main_kb())

# --- ТОП ДОНОРОВ ---
@dp.message(Command("top"))
async def top(m: types.Message):
    conn = sqlite3.connect('bot_data.db')
    rows = conn.execute('SELECT name, donated FROM users WHERE donated > 0 ORDER BY donated DESC LIMIT 10').fetchall()
    conn.close()
    if not rows: return await m.answer("Список героев пока пуст... 🌸")
    res = "🏆 **ГЕРОИ СЕРДЦА**\n\n"
    for i, (name, amt) in enumerate(rows, 1):
        res += f"{i}. {'👑' if amt >= 1000 else '👤'} {name} — {amt} ⭐\n"
    await m.answer(res, parse_mode="Markdown")

@dp.message(Command("status"))
async def status(m: types.Message):
    name, trust, donated = get_u(m.from_user.id)
    title = next((v for k, v in sorted(LEVELS.items(), reverse=True) if trust >= k), "Странник 🌫")
    vip = "🟡 **ЗОЛОТОЙ СКИН** 👑" if donated >= 1000 else "⚪ Путник"
    await m.answer(f"👤 Имя: {name}\n🆙 Ранг: {title}\n📈 Связь: {trust}\n💎: {vip}", parse_mode="Markdown")

# --- ИСПРАВЛЕННЫЙ ДОНАТ ---
@dp.message(F.text.lower().contains("отправить"))
async def donate(m: types.Message):
    num = re.search(r'\d+', m.text)
    if not num: return await m.answer("Напиши: `отправить 100` ⭐")
    amt = int(num.group())
    await bot.send_invoice(m.chat.id, "Дар Рыцарю", f"{amt} ⭐", "pay", "", "XTR", [LabeledPrice(label="⭐", amount=amt)])

@dp.pre_checkout_query()
async def pre(q: PreCheckoutQuery): await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.successful_payment)
async def success(m: types.Message):
    amt = m.successful_payment.total_amount
    conn = sqlite3.connect('bot_data.db')
    conn.execute('UPDATE users SET donated = donated + ?, trust = trust + ? WHERE uid = ?', (amt, amt*5, m.from_user.id))
    conn.commit(); conn.close()
    await m.answer("💖 **Твой дар согрел моё сердце!**")

user_modes = {}

@dp.message()
async def msg(m: types.Message):
    if not m.text or m.text.startswith("/"): return
    uid = m.from_user.id
    
    if m.text == "🤖 Пообщаться с ИИ":
        user_modes[uid] = "ai"
        return await m.answer("Я слушаю... 🥰", reply_markup=ReplyKeyboardBuilder().button(text="❌ Завершить диалог").as_markup(resize_keyboard=True))
    
    if m.text == "❌ Завершить диалог":
        user_modes.pop(uid, None)
        return await m.answer("Выбери путь:", reply_markup=main_kb())

    if user_modes.get(uid) == "ai":
        name, trust, donated = get_u(uid)
        conn = sqlite3.connect('bot_data.db')
        conn.execute('UPDATE users SET trust = trust + 1 WHERE uid = ?', (uid,))
        conn.commit(); conn.close()
        reply = await ask_knight(m.text, "Ваше Величество" if donated >= 1000 else name)
        await m.answer(reply)

async def main():
    init_db()
    await dp.start_polling(bot, allowed_updates=["message", "pre_checkout_query", "successful_payment"])

if __name__ == "__main__": asyncio.run(main())
