import asyncio
import sqlite3
import logging
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

# --- БЛОК БАЗЫ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages 
                      (message_id INTEGER PRIMARY KEY, user_id INTEGER)''')
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

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

# --- КЛАВИАТУРЫ ---
def get_main_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Поддержка")
    builder.button(text="Общение")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_exit_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Завершить диалог")
    return builder.as_markup(resize_keyboard=True)

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    add_user(message.from_user.id)
    await message.answer("Привет! Выбери нужный раздел:", reply_markup=get_main_kb())

@dp.message(F.text == "❌ Завершить диалог")
async def cmd_exit(message: types.Message):
    user_modes.pop(message.from_user.id, None)
    await message.answer("Диалог завершен.", reply_markup=get_main_kb())

@dp.message(F.text.lower().in_(["поддержка", "общение"]))
async def set_mode(message: types.Message):
    add_user(message.from_user.id)
    mode = "support" if "поддержка" in message.text.lower() else "chat"
    user_modes[message.from_user.id] = mode
    await message.answer(f"✅ Режим '{mode}' активен.", reply_markup=get_exit_kb())

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    text = message.text.replace("/broadcast", "").strip()
    if not text: return await message.answer("Напиши текст после команды.")
    users = get_all_users()
    for u_id in users:
        try:
            await bot.send_message(u_id, f"📢 <b>РАССЫЛКА:</b>\n\n{text}", parse_mode="HTML")
            await asyncio.sleep(0.05)
        except: pass
    await message.answer("✅ Рассылка завершена.")

# --- ПЕРЕСЫЛКА ОТ ПОЛЬЗОВАТЕЛЯ (ВСЕ ТИПЫ МЕДИА) ---
@dp.message(F.chat.type == "private")
async def handle_user_msg(message: types.Message):
    add_user(message.from_user.id)
    if message.text and (message.text.startswith("/") or message.text in ["Поддержка", "Общение", "❌ Завершить диалог"]):
        return

    mode = user_modes.get(message.from_user.id)
    target = GROUP_SUPPORT_ID if mode == "support" else GROUP_CHAT_ID if mode == "chat" else None
    
    if not target:
        return await message.answer("Пожалуйста, выбери раздел.", reply_markup=get_main_kb())

    try:
        # Метод forward сохраняет премиум-эффекты стикеров
        fwd_msg = await message.forward(chat_id=target)
        save_message_link(fwd_msg.message_id, message.from_user.id)
    except Exception as e:
        logging.error(f"Ошибка пересылки: {e}")

# --- УНИВЕРСАЛЬНЫЙ ОТВЕТ ИЗ ГРУППЫ ПОЛЬЗОВАТЕЛЮ ---
@dp.message((F.chat.id == GROUP_SUPPORT_ID) | (F.chat.id == GROUP_CHAT_ID))
async def handle_admin_reply(message: types.Message):
    if not message.reply_to_message:
        return

    user_id = get_user_by_msg(message.reply_to_message.message_id)
    if not user_id:
        return

    try:
        # Бот просто копирует любое сообщение админа (текст, стикер, премиум стикер, ГС) и шлет юзеру
        await message.copy_to(chat_id=user_id)
    except Exception as e:
        logging.error(f"Ошибка ответа: {e}")

async def main():
    init_db()
    print("Бот запущен! Премиум стикеры и все медиа поддерживаются.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except:
        print("Бот остановлен")
