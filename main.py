import asyncio
import sqlite3
import logging
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# --- НАСТРОЙКИ ---
API_TOKEN = '8418801272:AAG6KY8oRSdemGXhERo1vndcZTPdBvhUMLY'
ADMIN_ID = 8013668841 
GROUP_SUPPORT_ID = -1003587677334
GROUP_CHAT_ID = -1003519194282

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Глобальная переменная характера (по умолчанию — добрая помощница)
AI_CHARACTERS = {
    "current": "Ты — милая и добрая девушка-помощница. Ты сопереживаешь, используешь эмодзи и всегда поддерживаешь пользователя."
}

# --- БЛОК БАЗЫ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, user_name TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages 
                      (message_id INTEGER PRIMARY KEY, user_id INTEGER)''')
    conn.commit()
    conn.close()

def add_user(user_id, name=None):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    if name:
        cursor.execute('INSERT INTO users (user_id, user_name) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET user_name=?', (user_id, name, name))
    else:
        cursor.execute('INSERT OR IGNORE INTO users (user_id, user_name) VALUES (?, ?)', (user_id, "Друг"))
    conn.commit()
    conn.close()

def get_user_name(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_name FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else "Солнце"

def save_message_link(msg_id, user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO messages (message_id, user_id) VALUES (?, ?)', (msg_id, user_id))
    conn.commit()
    conn.close()

def get_user_by_msg(msg_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM messages WHERE message_id = ?', (msg_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_users():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]

user_modes = {}

# --- ИМИТАЦИЯ ГИБКОГО ХАРАКТЕРА ИИ ---
def get_ai_response(text, user_name):
    text = text.lower().strip()
    char = AI_CHARACTERS["current"].lower()
    
    # Смена имени
    if "зовут" in text or "моё имя" in text:
        new_name = text.split()[-1].replace("!", "").replace(".", "").capitalize()
        return f"запомнить_имя:{new_name}"

    # Если характер "Злой/Пират"
    if "пират" in char or "злой" in char:
        return f"Аррр, {user_name}! 🏴‍☠️ Твои слова как пустой сундук! Я ищу золото, а не болтовню. Что тебе нужно от старого морского волка?"
    
    # Если характер "Веселый"
    if "веселый" in char or "праздник" in char:
        return f"Ееее! 🎉 {user_name}, ты просто супер! Давай зажжем! Рассказывай что-нибудь крутое! 🚀"

    # Стандартный эмпатичный ответ (базовый)
    sad_words = ["плохо", "грустно", "устал", "тяжело"]
    if any(word in text for word in sad_words):
        return f"{user_name}, я чувствую твою боль... ✨ Я рядом, всё наладится. Ты сильный человек."
    
    return f"{user_name}, ты так интересно мыслишь! ✨ Расскажи мне об этом подробнее, я внимательно слушаю."

# --- ОБРАБОТЧИКИ КОМАНД АДМИНА ---

@dp.message(Command("set_ai"))
async def cmd_set_ai(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    new_prompt = message.text.replace("/set_ai", "").strip()
    if not new_prompt:
        return await message.answer("Напиши промт, например: /set_ai Ты — робот-дворецкий.")
    
    AI_CHARACTERS["current"] = new_prompt
    await message.answer(f"✅ Характер ИИ изменен для всех! Текущий промт:\n`{new_prompt}`", parse_mode="Markdown")

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    text = message.text.replace("/broadcast", "").strip()
    if not text: return
    users = get_all_users()
    for u_id in users:
        try: await bot.send_message(u_id, f"📢 **РАССЫЛКА:**\n\n{text}")
        except: pass
    await message.answer("✅ Рассылка завершена.")

# --- КЛАВИАТУРЫ ---
def get_main_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Поддержка")
    builder.button(text="Общение")
    builder.button(text="🤖 Пообщаться с ИИ")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_exit_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Завершить диалог")
    return builder.as_markup(resize_keyboard=True)

# --- ГЛАВНАЯ ЛОГИКА ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    add_user(message.from_user.id, message.from_user.first_name)
    await message.answer(f"Привет, {message.from_user.first_name}! 😊 Выбери раздел на кнопках ниже:", reply_markup=get_main_kb())

@dp.message(F.text == "❌ Завершить диалог")
async def cmd_exit(message: types.Message):
    user_modes.pop(message.from_user.id, None)
    await message.answer("Возвращаемся в меню. ✨", reply_markup=get_main_kb())

@dp.message(F.text.lower().in_(["поддержка", "общение", "🤖 пообщаться с ии"]))
async def set_mode(message: types.Message):
    add_user(message.from_user.id)
    text = message.text.lower()
    mode = "support" if "поддержка" in text else "chat" if "общение" in text else "ai"
    user_modes[message.from_user.id] = mode
    await message.answer(f"✅ Режим выбран! Слушаю тебя. ✨", reply_markup=get_exit_kb())

@dp.message(F.chat.type == "private")
async def handle_private(message: types.Message):
    add_user(message.from_user.id)
    if message.text and (message.text.startswith("/") or message.text in ["Поддержка", "Общение", "❌ Завершить диалог", "🤖 Пообщаться с ИИ"]):
        return

    mode = user_modes.get(message.from_user.id)
    
    if mode == "ai":
        if message.text:
            name = get_user_name(message.from_user.id)
            response = get_ai_response(message.text, name)
            if response.startswith("запомнить_имя:"):
                new_name = response.split(":")[1]
                add_user(message.from_user.id, new_name)
                await message.answer(f"Запомнила! Теперь ты для меня — {new_name}. ✨")
            else:
                await bot.send_chat_action(message.chat.id, "typing")
                await asyncio.sleep(0.8)
                await message.answer(response)
        return

    target = GROUP_SUPPORT_ID if mode == "support" else GROUP_CHAT_ID if mode == "chat" else None
    if target:
        try:
            fwd = await message.forward(chat_id=target)
            save_message_link(fwd.message_id, message.from_user.id)
        except: pass

@dp.message((F.chat.id == GROUP_SUPPORT_ID) | (F.chat.id == GROUP_CHAT_ID))
async def handle_admin_reply(message: types.Message):
    if message.reply_to_message:
        user_id = get_user_by_msg(message.reply_to_message.message_id)
        if user_id:
            try: await message.copy_to(chat_id=user_id)
            except: pass

async def main():
    init_db()
    print("Бот с управляемым характером запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
