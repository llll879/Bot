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

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, 
                       user_name TEXT, 
                       ai_prompt TEXT DEFAULT 'добрый помощник')''')
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

def update_user_ai(user_id, prompt):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET ai_prompt = ? WHERE user_id = ?', (prompt, user_id))
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_name, ai_prompt FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0] or "Друг", result[1] or "добрый помощник"
    return "Друг", "добрый помощник"

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

user_modes = {}

# --- УМНАЯ ЛОГИКА ИИ ---
def get_ai_response(text, user_name, user_prompt):
    text = text.lower().strip()
    p = user_prompt.lower()
    
    # Реакция на смену имени
    if "зовут" in text or "моё имя" in text:
        words = text.split()
        if len(words) > 1:
            return f"запомнить_имя:{words[-1].capitalize()}"

    # Логика персонажей
    if "пират" in p:
        return random.choice([f"Аррр, {user_name}! {text} — это достойная байка!", f"Пресная вода тебе в глотку, {user_name}! Говори по делу!"])
    if "котик" in p or "кот" in p:
        return random.choice([f"Мяу, {user_name}! *мурчит* Расскажи еще про '{text}'", f"Мрр... {user_name}, я тебя слушаю внимательно!"])
    if "гопник" in p:
        return f"Слышь, {user_name}, чё ты мне тут про '{text}' затираешь? Семки есть?"

    # Стандартные ответы (Fallback)
    return random.choice([
        f"{user_name}, это очень интересно! ✨",
        f"Я тебя поняла, {user_name}. 😊",
        f"Расскажи об этом побольше, {user_name}! ✨"
    ])

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

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    add_user(message.from_user.id, message.from_user.first_name)
    await message.answer(f"Привет, {message.from_user.first_name}! Выбери режим:", reply_markup=get_main_kb())

@dp.message(Command("my_ai"))
async def cmd_my_ai(message: types.Message):
    prompt = message.text.replace("/my_ai", "").strip()
    if not prompt: return await message.answer("Пример: `/my_ai злой пират`", parse_mode="Markdown")
    update_user_ai(message.from_user.id, prompt)
    await message.answer(f"✅ Теперь твой ИИ: {prompt}")

@dp.message(F.text == "❌ Завершить диалог")
async def cmd_exit(message: types.Message):
    user_modes.pop(message.from_user.id, None)
    await message.answer("Меню:", reply_markup=get_main_kb())

@dp.message(F.text.lower().in_(["поддержка", "общение", "🤖 пообщаться с ии"]))
async def set_mode(message: types.Message):
    add_user(message.from_user.id)
    text = message.text.lower()
    mode = "support" if "поддержка" in text else "chat" if "общение" in text else "ai"
    user_modes[message.from_user.id] = mode
    await message.answer(f"✅ Режим активен! Жду твоих сообщений. ✨", reply_markup=get_exit_kb())

@dp.message(F.chat.type == "private")
async def handle_private(message: types.Message):
    # Если это системная кнопка — игнорируем, чтобы не было дублей
    if message.text in ["Поддержка", "Общение", "🤖 Пообщаться с ИИ", "❌ Завершить диалог"]:
        return

    mode = user_modes.get(message.from_user.id)
    
    if mode == "ai":
        name, prompt = get_user_data(message.from_user.id)
        response = get_ai_response(message.text, name, prompt)
        
        if response.startswith("запомнить_имя:"):
            new_name = response.split(":")[1]
            add_user(message.from_user.id, new_name)
            await message.answer(f"Приятно познакомиться, {new_name}! ✨")
        else:
            await bot.send_chat_action(message.chat.id, "typing")
            await asyncio.sleep(0.5)
            await message.answer(response)
        return

    # Логика пересылки
    target = GROUP_SUPPORT_ID if mode == "support" else GROUP_CHAT_ID if mode == "chat" else None
    if target:
        fwd = await message.forward(chat_id=target)
        save_message_link(fwd.message_id, message.from_user.id)
    else:
        await message.answer("Сначала выбери режим на кнопках! 👇", reply_markup=get_main_kb())

@dp.message((F.chat.id == GROUP_SUPPORT_ID) | (F.chat.id == GROUP_CHAT_ID))
async def handle_admin_reply(message: types.Message):
    if message.reply_to_message:
        user_id = get_user_by_msg(message.reply_to_message.message_id)
        if user_id:
            try: await message.copy_to(chat_id=user_id)
            except: pass

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
