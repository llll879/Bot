import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery

# Конфигурация
TOKEN = "8043538908:AAEirXwCH31uljJYDRMODZ9iZ9i98AqjoyI"
GOLD_THRESHOLD = 1000 

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("donors.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS donors (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            total_stars INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def add_donation(user_id, username, amount):
    conn = sqlite3.connect("donors.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO donors (user_id, username, total_stars) 
        VALUES (?, ?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET 
        total_stars = total_stars + ?, 
        username = ?
    """, (user_id, username, amount, amount, username))
    conn.commit()
    conn.close()

def get_top_donors():
    conn = sqlite3.connect("donors.db")
    cur = conn.cursor()
    cur.execute("SELECT username, total_stars FROM donors ORDER BY total_stars DESC LIMIT 10")
    rows = cur.fetchall()
    conn.close()
    return rows

# --- ХЕНДЛЕРЫ БОТА ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Приветствую! Я — **Потерянный рыцарь**. 🛡️\n\n"
        "Вы можете поддержать меня Звездами.\n"
        "• Пожертвование от 1000 ⭐ открывает **Золотой статус**.\n"
        "• Команда /top покажет список героев-меценатов."
    )

@dp.message(Command("buy"))
async def show_shop(message: types.Message):
    await message.answer_invoice(
        title="Поддержка Потерянного рыцаря",
        description="Взнос в казну ордена. От 1000 звёзд — Золотой скин!",
        payload="stars_donation",
        currency="XTR",
        prices=[LabeledPrice(label="⭐ Звезды", amount=1000)],
        provider_token=""
    )

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def success_payment(message: types.Message):
    amount = message.successful_payment.total_amount
    user_id = message.from_user.id
    username = message.from_user.full_name or f"ID: {user_id}"

    # Сохраняем в ТОП
    add_donation(user_id, username, amount)

    msg = f"Благодарю за щедрость, {username}! Вы внесли {amount} ⭐."
    if amount >= GOLD_THRESHOLD:
        msg += "\n\n✨ **ВАМ ВЫДАН ЗОЛОТОЙ СКИН!** ✨"
    
    await message.answer(msg)

@dp.message(Command("top"))
async def show_top(message: types.Message):
    top = get_top_donors()
    if not top:
        return await message.answer("Список доноров пуст. Станьте первым!")

    text = "🏆 **ТОП ДОНОРОВ ПОТЕРЯННОГО РЫЦАРЯ:**\n\n"
    for i, (name, stars) in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
        text += f"{medal} {i}. {name} — {stars} ⭐\n"
    
    await message.answer(text)

# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    # Удаляем вебхук, чтобы исправить вашу ошибку "Conflict"
    await bot.delete_webhook(drop_pending_updates=True)
    print("Потерянный рыцарь готов к приему звезд...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
