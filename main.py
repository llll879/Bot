import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# --- НАСТРОЙКИ (ОБЯЗАТЕЛЬНО ЗАПОЛНИТЬ) ---
API_TOKEN = '8418801272:AAG6KY8oRSdemGXhERo1vndcZTPdBvhUMLY'
ADMIN_ID = 8013668841  # Ваш ID
GROUP_SUPPORT_ID = -1003587677334  # Исправлено: просто число
GROUP_CHAT_ID = -1003519194282     # Исправлено: просто число

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- БЛОК БАЗЫ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]

# Словарь для режимов
user_modes = {}

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    add_user(message.from_user.id)  # Запись в базу для рассылки
    await message.answer(
        "Привет! Напиши нашим админам, они ждут тебя.\n\n"
        "⚠️ **ВАЖНО:** выбери 'поддержка' или 'общение', иначе админы не получат твои сообщения."
    )

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    # Текст после команды /broadcast
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("❌ Ошибка: введите текст. Пример: `/broadcast Привет всем`", parse_mode="Markdown")
        return

    users = get_all_users()
    await message.answer(f"📢 Запускаю рассылку на {len(users)} пользователей...")

    success = 0
    for u_id in users:
        try:
            await bot.send_message(u_id, text)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    
    await message.answer(f"✅ Готово! Получили: {success} чел.")

@dp.message(F.text.lower() == "поддержка")
async def set_mode_support(message: types.Message):
    user_modes[message.from_user.id] = "support"
    await message.answer("Солнце, подожди чуть-чуть, и наши админы из **поддержки** тебе ответят.")

@dp.message(F.text.lower() == "общение")
async def set_mode_chat(message: types.Message):
    user_modes[message.from_user.id] = "chat"
    await message.answer("Солнце, режим **общения** активен. Напиши что-нибудь, и админы скоро ответят.")

# --- ПЕРЕСЫЛКА СООБЩЕНИЙ ---

@dp.message(F.chat.type == "private")
async def handle_forwarding(message: types.Message):
    # Пропускаем команды и ключевые слова
    if message.text and (message.text.lower() in ["поддержка", "общение"] or message.text.startswith("/")):
        return

    mode = user_modes.get(message.from_user.id)
    
    if mode == "support":
        target = GROUP_SUPPORT_ID
        header_text = "🆘 Сообщение в ПОДДЕРЖКУ"
    elif mode == "chat":
        target = GROUP_CHAT_ID
        header_text = "💬 Сообщение в ОБЩЕНИЕ"
    else:
        await message.answer("Пожалуйста, сначала выбери 'поддержка' или 'общение'.")
        return

    try:
        # 1. Отправляем текстовое уведомление
        await bot.send_message(target, f"📩 **{header_text}**\nОт: {message.from_user.full_name}")
        
        # 2. ПЕРЕСЫЛКА (с плашкой Telegram)
        await message.forward(chat_id=target)
        
        await message.answer("✅ Отправлено! Ожидай ответа.")
    except Exception as e:
        logging.error(f"Ошибка пересылки: {e}")
        await message.answer("❌ Ошибка: бот не может отправить сообщение в группу. Проверь, что он там администратор.")

# --- ЗАПУСК ---
async def main():
    init_db()
    print("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")
