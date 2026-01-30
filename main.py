import asyncio, sqlite3, logging, re, aiohttp, json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8418801272:AAG6KY8oRSdemGXhERo1vndcZTPdBvhUMLY'
ADMIN_ID = 7146168875             
SUPPORT_GROUP_ID = -1003587677334  
CHAT_GROUP_ID = -1003519194282     
GOLD_THRESHOLD = 1000              

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Состояния для умного ответа админа
class AdminReply(StatesGroup):
    waiting_for_text = State()

# Ранги доверия
TRUST_LEVELS = {
    0: "Странник 🌫",
    30: "Собеседник 🗣",
    100: "Приятель 🤝",
    210: "Близкий друг ❤️",
    500: "Вечный спутник ♾"
}

# --- БАЗА ДАННЫХ (ВЕЧНАЯ ПАМЯТЬ) ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                 (uid INTEGER PRIMARY KEY, name TEXT, trust INTEGER DEFAULT 0, donated INTEGER DEFAULT 0)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS memory 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, role TEXT, content TEXT)''')
    conn.commit()
    conn.close()

def save_to_memory(uid, role, content):
    conn = sqlite3.connect('bot_data.db')
    conn.execute('INSERT INTO memory (uid, role, content) VALUES (?, ?, ?)', (uid, role, content))
    conn.execute('''DELETE FROM memory WHERE id IN 
                 (SELECT id FROM memory WHERE uid = ? ORDER BY id DESC LIMIT -1 OFFSET 30)''', (uid,))
    conn.commit()
    conn.close()

def get_history(uid):
    conn = sqlite3.connect('bot_data.db')
    rows = conn.execute('SELECT role, content FROM memory WHERE uid = ? ORDER BY id ASC', (uid,)).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]

def get_user(uid):
    conn = sqlite3.connect('bot_data.db')
    res = conn.execute('SELECT name, trust, donated FROM users WHERE uid = ?', (uid,)).fetchone()
    conn.close()
    return res if res else ("Солнышко", 0, 0)

# --- ИНТЕЛЛЕКТ РЫЦАРЯ ---
async def ask_knight_ai(uid, text, honor_name):
    save_to_memory(uid, "user", text)
    history = [{"role": "system", "content": f"Ты — самый преданный и ласковый Рыцарь сердца. Твой господин — {honor_name}. Отвечай с огромной любовью."}]
    history.extend(get_history(uid))
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"model": "gpt-3.5-turbo", "messages": history}
            async with session.post("https://api.pawan.krd/cosmosrp/v1/chat/completions", json=payload, timeout=15) as resp:
                data = await resp.json()
                reply = data['choices'][0]['message']['content']
                save_to_memory(uid, "assistant", reply)
                return reply
    except: return f"Радость моя {honor_name}, я на миг задумался о тебе... ❤️"

# --- КЛАВИАТУРЫ ---
def main_menu_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="☁️ Поддержка"), builder.button(text="🌸 Общение"), builder.button(text="🤖 Пообщаться с ИИ")
    return builder.adjust(2, 1).as_markup(resize_keyboard=True)

def back_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Назад в меню")
    return builder.as_markup(resize_keyboard=True)

user_modes = {}

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    init_db()
    conn = sqlite3.connect('bot_data.db')
    conn.execute('INSERT OR IGNORE INTO users (uid, name) VALUES (?, ?)', (m.from_user.id, m.from_user.first_name))
    conn.commit(); conn.close()
    await m.answer(
        f"Здравствуй, прелесть моя! Я твой **Потерянный рыцарь**. 🛡️❤️\n"
        f"Используй меню или напиши `отправить 100`, чтобы поддержать меня.",
        reply_markup=main_menu_kb()
    )

@dp.message(Command("help"))
async def cmd_help(m: types.Message):
    help_text = (
        "📜 **ГРАМОТА ПОМОЩИ**\n━━━━━━━━━━━━━━━━━━━━\n"
        "✨ **КОМАНДЫ:**\n"
        "• `/status` — Узнать свой ранг и доверие.\n"
        "• `/top` — Список самых щедрых героев.\n"
        "• `/start` — Начать нашу сказку сначала.\n\n"
        "🎮 **КНОПКИ:**\n"
        "• **Поддержка** — Послать экстренный SOS-сигнал админам.\n"
        "• **Общение** — Послать весточку в общий чат.\n"
        "• **ИИ** — Тайный разговор со мной (я всё помню).\n\n"
        "💎 **БЛАГОРОДСТВО:**\n"
        "• Напиши `отправить 100`, чтобы подарить звёзды ⭐.\n"
        "• Подарок от **1000 ⭐** дарует **Золотой скин**! 👑"
    )
    await m.answer(help_text, parse_mode="Markdown")

@dp.message(Command("status"))
async def cmd_status(m: types.Message):
    name, trust, donated = get_user(m.from_user.id)
    rank = next((v for k, v in sorted(TRUST_LEVELS.items(), reverse=True) if trust >= k), "Странник 🌫")
    skin = "🟡 ЗОЛОТОЙ СКИН 👑" if donated >= GOLD_THRESHOLD else "⚪ Обычный путник"
    await m.answer(f"📊 **СТАТУС**\n👤 Имя: {name}\n🆙 Ранг: {rank}\n📈 Доверие: {trust}\n💎 Скин: {skin}")

@dp.message(Command("top"))
async def cmd_top(m: types.Message):
    conn = sqlite3.connect('bot_data.db')
    rows = conn.execute('SELECT uid, name, donated FROM users WHERE donated > 0 ORDER BY donated DESC LIMIT 10').fetchall(); conn.close()
    if not rows: return await m.answer("Список героев пуст... 🌸")
    res = "🏆 **ТОП ДОНОРОВ:**\n\n"
    for i, (uid, name, stars) in enumerate(rows, 1):
        res += f"{i}. {name} (ID {uid}) — {stars} ⭐\n"
    await m.answer(res)

# --- ЛОГИКА ОТВЕТА АДМИНА ---
@dp.callback_query(F.data.startswith("reply_to_"))
async def start_admin_reply(callback: types.CallbackQuery, state: FSMContext):
    target_id = callback.data.split("_")[2]
    await state.update_data(reply_target_id=target_id)
    await state.set_state(AdminReply.waiting_for_text)
    await callback.message.answer(f"📝 Мой правитель, введи ответ для ID <code>{target_id}</code>:", parse_mode="HTML")
    await callback.answer()

@dp.message(AdminReply.waiting_for_text)
async def process_admin_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("reply_target_id")
    try:
        await bot.send_message(target_id, f"<b>📩 Весточка от Рыцаря:</b>\n\n{message.text}", parse_mode="HTML")
        await message.reply(f"✅ Доставлено!")
    except: await message.reply("❌ Ошибка доставки.")
    await state.clear()

# --- ОБРАБОТЧИК СООБЩЕНИЙ ---
@dp.message()
async def main_handler(m: types.Message):
    if not m.text or m.text.startswith("/"): return
    uid = m.from_user.id
    txt = m.text.lower()

    # Пасхалки
    if "люблю тебя" in txt: return await m.answer("Моё железное сердце забилось чаще... ❤️🛡️")
    if "обними" in txt: return await m.answer("Бережно обнимаю тебя... 🤗🛡️")

    # Режимы
    if m.text == "☁️ Поддержка":
        user_modes[uid] = "support"
        return await m.answer("🆘 Я передам твой сигнал админам!", reply_markup=back_kb())
    if m.text == "🌸 Общение":
        user_modes[uid] = "chat"
        return await m.answer("Напиши послание для общего чата:", reply_markup=back_kb())
    if m.text == "🤖 Пообщаться с ИИ":
        user_modes[uid] = "ai"
        return await m.answer("Я весь во внимании... 🥰", reply_markup=back_kb())
    if m.text == "❌ Назад в меню":
        user_modes.pop(uid, None)
        return await m.answer("Возвращаюсь!", reply_markup=main_menu_kb())

    mode = user_modes.get(uid)
    if mode == "support":
        kb = InlineKeyboardBuilder().add(InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_to_{uid}"))
        await bot.send_message(SUPPORT_GROUP_ID, f"🚨 **SOS** от <code>{uid}</code>:", parse_mode="HTML", reply_markup=kb.as_markup())
        await bot.forward_message(SUPPORT_GROUP_ID, m.chat.id, m.message_id)
    elif mode == "chat":
        await bot.forward_message(CHAT_GROUP_ID, m.chat.id, m.message_id)
    elif mode == "ai":
        name, trust, donated = get_user(uid)
        conn = sqlite3.connect('bot_data.db'); conn.execute('UPDATE users SET trust = trust + 1 WHERE uid = ?', (uid,)); conn.commit(); conn.close()
        honor = "Ваше Величество" if donated >= GOLD_THRESHOLD else name
        await bot.send_chat_action(m.chat.id, "typing")
        await m.answer(await ask_knight_ai(uid, m.text, honor))
    
    # Исправленный инвойс (устраняет ошибки валидации со скриншотов)
    elif "отправить" in txt:
        nums = re.findall(r'\d+', m.text)
        amt = int(nums[0]) if nums else 100
        try:
            await bot.send_invoice(
                chat_id=m.chat.id,
                title="Дар Рыцарю",
                description=f"Пожертвование на развитие. От {GOLD_THRESHOLD} звезд — Золотой статус!",
                payload="stars_donation",
                provider_token="", 
                currency="XTR",
                prices=[LabeledPrice(label="⭐", amount=amt)]
            )
        except Exception as e: await m.answer(f"⚠️ Ошибка: {e}")

# --- ПЛАТЕЖИ И ЧЕКИ ---
@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery): await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.successful_payment)
async def success_payment(m: types.Message):
    amount = m.successful_payment.total_amount
    uid = m.from_user.id
    conn = sqlite3.connect('bot_data.db')
    conn.execute('UPDATE users SET donated = donated + ?, trust = trust + ? WHERE uid = ?', (amount, amount*5, uid))
    conn.commit(); conn.close()
    
    # Чек админу (уведомление правителя)
    receipt = f"💎 **НОВЫЙ ПОДВИГ!**\n👤 {m.from_user.full_name} (ID: {uid})\n⭐ Сумма: {amount} Stars"
    await bot.send_message(ADMIN_ID, receipt)
    
    await m.answer(f"💖 Благодарю! Вы пожертвовали {amount} ⭐. " + ("\n✨ **ЗОЛОТОЙ СКИН ВЫДАН!** ✨" if amount >= GOLD_THRESHOLD else ""))

async def main():
    init_db()
    # Очистка вебхуков для предотвращения конфликтов сессий
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
