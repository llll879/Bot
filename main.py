import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- НАСТРОЙКИ ---
API_TOKEN = '8418801272:AAG6KY8oRSdemGXhERo1vndcZTPdBvhUMLY'
ADMIN_ID = 8013668841  # ВАШ ID (для рассылок)
GROUP_SUPPORT_ID = -1003587677334  # Группа "Поддержка"
GROUP_CHAT_ID = -1003519194282     # Группа "Общение"

# Настройка логирования
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Состояния для рассылки
class BroadcastStates(StatesGroup):
    waiting_for_content = State()

# --- РАБОТА С БАЗОЙ ДАННЫХ (SQLite) ---
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    # Таблица для связи сообщений (чтобы админ мог отвечать пользователю)
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages 
                      (msg_in_group INTEGER, user_id INTEGER)''')
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def save_msg_relation(msg_id, user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO messages VALUES (?, ?)', (msg_id, user_id))
    conn.commit()
    conn.close()

def get_user_by_msg(msg_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM messages WHERE msg_in_group = ?', (msg_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def get_all_users():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    add_user(message.from_user.id)
    await message.answer(
        "👋 Привет!\n\n"
        "напиши *поддержка* если хочешь чтобы тебя поддержали\n"
        "Напиши *общение* если хочешь просто поболтать"
    )

# Выбор режима
user_sessions = {}

@dp.message(F.text.lower().in_(["поддержка", "общение"]))
async def set_mode(message: types.Message):
    mode = message.text.lower()
    target = GROUP_SUPPORT_ID if mode == "поддержка" else GROUP_CHAT_ID
    user_sessions[message.from_user.id] = target
    await message.answer(f"✅ Режим '{mode}' активирован. Пишите сообщение — я его перешлю.")

# --- РАССЫЛКА (ТОЛЬКО АДМИН) ---

@dp.message(Command("broadcast"), F.from_user.id == ADMIN_ID)
async def start_broadcast(message: types.Message, state: FSMContext):
    await message.answer("Отправьте то, что нужно разослать (текст, фото или фото с текстом).")
    await state.set_state(BroadcastStates.waiting_for_content)

@dp.message(BroadcastStates.waiting_for_content, F.from_user.id == ADMIN_ID)
async def perform_broadcast(message: types.Message, state: FSMContext):
    users = get_all_users()
    count = 0
    await message.answer(f"🚀 Начинаю рассылку...")
    for user_id in users:
        try:
            await message.copy_to(chat_id=user_id)
            count += 1
            await asyncio.sleep(0.05)
        except: continue
    await message.answer(f"✅ Готово! Получили: {count} чел.")
    await state.clear()

# --- ПЕРЕСЫЛКА СООБЩЕНИЙ ---

# Из ЛС в Группу
@dp.message(F.chat.type == "private")
async def forward_to_group(message: types.Message):
    target = user_sessions.get(message.from_user.id)
    if not target:
        await message.answer("Сначала напишите 'поддержка' или 'общение'.")
        return
    
    # Копируем сообщение в группу
    sent = await message.copy_to(chat_id=target)
    # Сохраняем связь, чтобы знать кому отвечать
    save_msg_relation(sent.message_id, message.from_user.id)

# Из Группы пользователю (ОТВЕТ)
@dp.message((F.chat.id == GROUP_SUPPORT_ID) | (F.chat.id == GROUP_CHAT_ID))
async def reply_to_user(message: types.Message):
    if message.reply_to_message:
        user_id = get_user_by_msg(message.reply_to_message.message_id)
        if user_id:
            try:
                await message.copy_to(chat_id=user_id)
            except:
                await message.reply("❌ Не удалось отправить ответ (бот заблокирован).")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
