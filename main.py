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
    await message.answer(
        "Привет! Выбери нужный раздел на кнопках ниже:",
        reply_markup=get_main_kb()
    )

@dp.message(F.text == "❌ Завершить диалог")
async def cmd_exit(message: types.Message):
    user_modes.pop(message.from_user.id, None)
    await message.answer("Диалог завершен. Вы вернулись в главное меню.", reply_markup=get_main_kb())

@dp.message(F.text.lower().in_(["поддержка", "общение"]))
async def set_mode(message: types.Message):
    mode = "support" if "поддержка" in message.text.lower() else "chat"
    user_modes[message.from_user.id] = mode
    await message.answer(
        f"✅ Режим '{mode}' активен. Теперь всё, что ты напишешь, улетит админам.",
        reply_markup=get_exit_kb()
    )

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    text = message.text.replace("/broadcast", "").strip()
    if not text: return await message.answer("Напиши текст: /broadcast Привет")
    users = get_all_users()
    success = 0
    for u_id in users:
        try:
            await bot.send_message(u_id, f"📢 <b>РАССЫЛКА:</b>\n\n{text}", parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ Готово! Получили: {success}")

# --- ПЕРЕСЫЛКА ОТ ПОЛЬЗОВАТЕЛЯ ---
@dp.message(F.chat.type == "private")
async def handle_user_msg(message: types.Message):
    if message.text and (message.text.startswith("/") or message.text in ["Поддержка", "Общение", "❌ Завершить диалог"]):
        return

    mode = user_modes.get(message.from_user.id)
    target = GROUP_SUPPORT_ID if mode == "support" else GROUP_CHAT_ID if mode == "chat" else None
    
    if not target:
        return await message.answer("Пожалуйста, выбери раздел на кнопках.", reply_markup=get_main_kb())

    try:
        header = "🆘 ПОДДЕРЖКА" if mode == "support" else "💬 ОБЩЕНИЕ"
        await bot.send_message(target, f"📩 <b>{header}</b>\nОт: {message.from_user.full_name}")
        fwd_msg = await message.forward(chat_id=target)
        save_message_link(fwd_msg.message_id, message.from_user.id)
        await message.answer("🚀 Доставлено!")
    except Exception as e:
        await message.answer(f"Ошибка отправки: {e}")

# --- ОТВЕТ ИЗ ГРУППЫ ---
@dp.message((F.chat.id == GROUP_SUPPORT_ID) | (F.chat.id == GROUP_CHAT_ID))
async def handle_admin_reply(message: types.Message):
    if message.reply_to_message:
        user_id = get_user_by_msg(message.reply_to_message.message_id)
        if user_id:
            try:
                if message.text:
                    await bot.send_message(user_id, f"<b>Админ ответил:</b>\n{message.text}", parse_mode="HTML")
                elif message.photo:
                    await bot.send_photo(user_id, message.photo[-1].file_id, caption=f"<b>Ответ админа:</b>\n{message.caption or ''}", parse_mode="HTML")
                await message.reply("✅ Ответ отправлен!")
            except:
                await message.reply("❌ Не удалось отправить (бот заблокирован?)")

async def main():
    init_db()
    print("Бот запущен с кнопками выхода!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
