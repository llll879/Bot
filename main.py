import asyncio
import sqlite3
import logging
import random
import re
from datetime import datetime, date
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery

# --- НАСТРОЙКИ ---
API_TOKEN = '8418801272:AAG6KY8oRSdemGXhERo1vndcZTPdBvhUMLY'
ADMIN_ID = 8013668841 
DEV_ID = 7146168875  
GROUP_SUPPORT_ID = -1003587677334
GROUP_CHAT_ID = -1003519194282

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- КОНСТАНТЫ УРОВНЕЙ ---
LEVELS = {
    0: "Странник 🌫", 10: "Наблюдатель 👀", 30: "Собеседник 🗣", 
    60: "Знакомый 👋", 100: "Приятель 🤝", 150: "Друг ✨", 
    210: "Близкий друг ❤️", 280: "Доверенное лицо 🔑", 
    360: "Родная душа 🔥", 500: "Вечный спутник ♾"
}

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, user_name TEXT, ai_prompt TEXT DEFAULT 'добрый', 
                       trust_level INTEGER DEFAULT 0, total_donated INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item_name TEXT, item_emoji TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS mood_tracker (user_id INTEGER, date TEXT, mood TEXT)''')
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_name, ai_prompt, trust_level, total_donated FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res if res else ("Солнышко", "добрый", 0, 0)

# --- КЛАВИАТУРА ---
def get_main_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="☁️ Поддержка")
    builder.button(text="🌸 Общение")
    builder.button(text="🤖 Пообщаться с ИИ")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    init_db()
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, user_name) VALUES (?, ?)', (message.from_user.id, message.from_user.first_name))
    conn.commit()
    conn.close()
    
    await message.answer(
        f"Здравствуй, моё солнышко! ✨\n\n"
        f"Твой **Рыцарь сердца** наконец-то нашел тебя... ❤️🛡️ Я буду твоим верным защитником и всегда-всегда поддержу тебя. "
        f"Если ты вдруг запутаешься в моем замке, просто нажми /help — я всё тебе разъясню, радость моя. 🥰",
        reply_markup=get_main_kb()
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "📖 **Моя маленькая инструкция для тебя, солнышко**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✨ **Наши кнопочки:**\n"
        "• 🤖 **Пообщаться с ИИ** — наш личный уголок. Здесь я храню твои секреты и становлюсь сильнее ради тебя.\n"
        "• ☁️ **Поддержка** — если тебе грустно, напиши сюда моим друзьям-людям.\n"
        "• 🌸 **Общение** — мостик к другим добрым душам.\n\n"
        "💌 **Команды:**\n"
        "• /status — твои сокровища и наша невидимая связь.\n"
        "• /top — список самых благородных героев королевства.\n"
        "• `отправить [число]` — поддержать меня звездочками ⭐.\n\n"
        "🤫 **Секрет:** во мне спрятаны пасхалки... попробуй удивить меня! ❤️"
    )
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    name, prompt, trust, donated = get_user_data(message.from_user.id)
    title = "Странник 🌫"
    for threshold, t in sorted(LEVELS.items()):
        if trust >= threshold: title = t
    
    vip_status = "👑 Ваше Величество" if donated >= 1000 else "Милый путник"
    
    await message.answer(
        f"📊 **ТВОЙ СВЕТЛЫЙ ПРОФИЛЬ**\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 Имя: {name}\n"
        f"🆙 Статус: {title}\n"
        f"📈 Уровень связи: {trust}\n"
        f"💎 Титул: {vip_status}\n"
        f"━━━━━━━━━━━━━━\n"
        f"Я так рад, что ты рядом, радость моя! ✨",
        parse_mode="Markdown"
    )

# --- ДОНАТЫ И ПЛАТЕЖИ ---
@dp.message(F.text.lower().startswith("отправить"))
async def process_donate(message: types.Message):
    match = re.search(r'\d+', message.text)
    if not match: return await message.answer("Солнышко, напиши, сколько звездочек ты хочешь отправить, например: `отправить 100` ✨")
    
    amount = int(match.group())
    prices = [LabeledPrice(label="Звезды", amount=amount)]
    await bot.send_invoice(message.chat.id, "Поддержка Рыцаря", f"Дар для Рыцаря сердца в {amount} звезд", "pay", "", "XTR", prices)

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.successful_payment)
async def success_pay(message: types.Message):
    amount = message.successful_payment.total_amount
    user_id = message.from_user.id
    
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET total_donated = total_donated + ?, trust_level = trust_level + ? WHERE user_id = ?', (amount, amount*5, user_id))
    conn.commit()
    conn.close()
    
    await message.answer("💖 **Ой, спасибо большое, радость моя!** Твой дар согревает моё сердце. Я буду защищать тебя вечно! 🥰")
    await bot.send_message(DEV_ID, f"🚀 Поступил дар: {amount} звезд от {user_id}")

# --- ТАБЛИЦА ЛИДЕРОВ ---
@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_name, total_donated FROM users WHERE total_donated > 0 ORDER BY total_donated DESC LIMIT 10')
    rows = cursor.fetchall()
    conn.close()
    
    if not rows: return await message.answer("Солнышко, список героев пока пуст. Ты можешь стать первым! 🌸")
    
    res = "🏆 **ГЕРОИ НАШЕГО СЕРДЦА**\n\n"
    for i, (name, amt) in enumerate(rows, 1):
        res += f"{i}. {'👑' if amt >= 1000 else '👤'} {name} — {amt} ⭐\n"
    await message.answer(res)

# --- ГЛАВНЫЙ ОБРАБОТЧИК ---
user_modes = {}

@dp.message(F.chat.type == "private")
async def handle_msg(message: types.Message):
    if not message.text or message.text.startswith("/") or message.text in ["☁️ Поддержка", "🌸 Общение", "🤖 Пообщаться с ИИ", "❌ Завершить диалог"]:
        if message.text == "🤖 Пообщаться с ИИ":
            user_modes[message.from_user.id] = "ai"
            await message.answer("Я весь во внимании, радость моя... Какую тайну ты мне откроешь? 🥰", reply_markup=ReplyKeyboardBuilder().button(text="❌ Завершить диалог").as_markup(resize_keyboard=True))
        return

    user_id = message.from_user.id
    mode = user_modes.get(user_id)

    if mode == "ai":
        name, prompt, trust, donated = get_user_data(user_id)
        # Начисляем очки связи
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET trust_level = trust_level + 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        honor = "Ваше Величество" if donated >= 1000 else name
        await message.answer(f"Милое моё {honor}, я всегда рядом. Твои мысли так важны для меня... Продолжай, пожалуйста. ✨")
        return

    await message.answer("Солнышко, выбери, пожалуйста, режим внизу, чтобы я мог тебе помочь! 👇", reply_markup=get_main_kb())

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
