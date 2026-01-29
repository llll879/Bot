import asyncio, sqlite3, logging, re, aiohttp, json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8418801272:AAG6KY8oRSdemGXhERo1vndcZTPdBvhUMLY'
ADMIN_ID = 7146168875             # Твой ID
SUPPORT_GROUP_ID = -1003587677334  # Группа поддержки
CHAT_GROUP_ID = -1003519194282     # Группа общения

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

# --- ИНТЕЛЛЕКТ РЫЦАРЯ (AI С ПАМЯТЬЮ) ---
async def ask_knight_ai(uid, text, honor_name):
    save_to_memory(uid, "user", text)
    history = [{"role": "system", "content": f"Ты — ласковый Рыцарь сердца. Твой господин — {honor_name}. Ты помнишь историю бесед."}]
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
    builder.button(text="☁️ Поддержка"), builder.button(text="🌸 Общение")
    builder.button(text="🤖 Пообщаться с ИИ")
    return builder.adjust(2, 1).as_markup(resize_keyboard=True)

def back_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Назад в меню")
    return builder.as_markup(resize_keyboard=True)

user_modes = {}

# --- ЛОГИКА ОТВЕТА ЧЕРЕЗ КНОПКУ ---
@dp.callback_query(F.data.startswith("reply_to_"))
async def start_admin_reply(callback: types.CallbackQuery, state: FSMContext):
    target_id = callback.data.split("_")[2]
    await state.update_data(reply_target_id=target_id)
    await state.set_state(AdminReply.waiting_for_text)
    await callback.message.answer(f"📝 Мой правитель, введи ответ для души с ID <code>{target_id}</code>:", parse_mode="HTML")
    await callback.answer()

@dp.message(AdminReply.waiting_for_text)
async def process_admin_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("reply_target_id")
    try:
        await bot.send_message(target_id, f"<b>📩 Весточка от Рыцаря:</b>\n\n{message.text}", parse_mode="HTML")
        await message.reply(f"✅ Твоё слово доставлено!")
    except:
        await message.reply("❌ Не удалось доставить.")
    await state.clear()

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    init_db()
    conn = sqlite3.connect('bot_data.db')
    conn.execute('INSERT OR IGNORE INTO users (uid, name) VALUES (?, ?)', (m.from_user.id, m.from_user.first_name))
    conn.commit(); conn.close()
    await m.answer(f"Здравствуй, прелесть моя! Я твой Рыцарь сердца. ❤️🛡️", reply_markup=main_menu_kb())

@dp.message(Command("help"))
async def cmd_help(m: types.Message):
    help_text = (
        "📜 **ГРАМОТА ВЕРНОГО РЫЦАРЯ**\n━━━━━━━━━━━━━━━━━━━━\n"
        "✨ **ТВОИ СЕКРЕТЫ:**\n"
        "• `/status` — Узнать свой ранг и уровень доверия.\n"
        "• `/top` — Взглянуть на самых щедрых героев.\n"
        "• `/start` — Вернуться к началу нашей сказки.\n\n"
        "🎮 **ВОЛШЕБНЫЕ КНОПКИ:**\n"
        "• **☁️ Поддержка** — Послать SOS-сигнал админам.\n"
        "• **🌸 Общение** — Твои слова в общий чат.\n"
        "• **🤖 Пообщаться с ИИ** — Разговор со мной (я всё помню).\n\n"
        "💎 **БЛАГОРОДСТВО:**\n"
        "• Напиши `отправить 100`, чтобы подарить мне звёзды ⭐.\n"
        "• Дар от **1000 ⭐** открывает **Золотой скин**! 👑"
    )
    await m.answer(help_text, parse_mode="Markdown")

@dp.message(Command("status"))
async def cmd_status(m: types.Message):
    name, trust, donated = get_user(m.from_user.id)
    rank = next((v for k, v in sorted(TRUST_LEVELS.items(), reverse=True) if trust >= k), "Странник 🌫")
    skin = "🟡 ЗОЛОТОЙ СКИН 👑" if donated >= 1000 else "⚪ Обычный путник"
    await m.answer(f"📊 **ТВОЙ СТАТУС**\n👤 Имя: {name}\n🆙 Ранг: {rank}\n📈 Доверие: {trust}\n💎 Скин: {skin}")

@dp.message(Command("top"))
async def cmd_top(m: types.Message):
    conn = sqlite3.connect('bot_data.db')
    rows = conn.execute('SELECT name, donated FROM users WHERE donated > 0 ORDER BY donated DESC LIMIT 10').fetchall()
    conn.close()
    if not rows: return await m.answer("Список героев пуст... 🌸")
    res = "🏆 **ВЕЛИЧАЙШИЕ ГЕРОИ СЕРДЦА**\n\n"
    for i, (name, amt) in enumerate(rows, 1):
        icon = "👑" if amt >= 1000 else "👤"
        res += f"{i}. {icon} {name} — {amt} ⭐\n"
    await m.answer(res)

@dp.message(Command("send"))
async def admin_broadcast(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    if not command.args: return await message.answer("⚠️ Напиши: `/send [текст]`")
    conn = sqlite3.connect('bot_data.db')
    users = conn.execute('SELECT uid FROM users').fetchall(); conn.close()
    for user in users:
        try: await bot.send_message(user[0], command.args); await asyncio.sleep(0.05)
        except: pass
    await message.answer("✅ Весть разнесена!")

# --- ОБРАБОТЧИК ---
@dp.message()
async def main_handler(m: types.Message):
    if not m.text or m.text.startswith("/"): return
    uid = m.from_user.id
    txt = m.text.lower()

    # ПАСХАЛКИ
    if "люблю тебя" in txt or "ты лучший" in txt:
        return await m.answer("Моё железное сердце забилось чаще... ❤️🛡️")
    if "кто ты" in txt:
        return await m.answer("Я твой верный Потерянный рыцарь. ✨")
    if "обними" in txt:
        return await m.answer("Я бережно обнимаю тебя своими доспехами... 🤗🛡️")

    # Режимы
    if m.text == "☁️ Поддержка":
        user_modes[uid] = "support"
        return await m.answer("🆘 Доверь мне свою тревогу!", reply_markup=back_kb())
    if m.text == "🌸 Общение":
        user_modes[uid] = "chat"
        return await m.answer("Напиши своё послание для общего чата:", reply_markup=back_kb())
    if m.text == "🤖 Пообщаться с ИИ":
        user_modes[uid] = "ai"
        return await m.answer("Я весь превратился в слух... 🥰", reply_markup=back_kb())
    if m.text == "❌ Назад в меню":
        user_modes.pop(uid, None)
        return await m.answer("Возвращаюсь!", reply_markup=main_menu_kb())

    mode = user_modes.get(uid)
    
    if mode == "support":
        kb = InlineKeyboardBuilder()
        kb.add(InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_to_{uid}"))
        await bot.send_message(SUPPORT_GROUP_ID, f"🚨 **SOS** от <code>{uid}</code> (@{m.from_user.username or 'none'}):", parse_mode="HTML", reply_markup=kb.as_markup())
        await bot.forward_message(SUPPORT_GROUP_ID, m.chat.id, m.message_id)
        
    elif mode == "chat":
        await bot.forward_message(CHAT_GROUP_ID, m.chat.id, m.message_id)
        
    elif mode == "ai":
        name, trust, donated = get_user(uid)
        conn = sqlite3.connect('bot_data.db'); conn.execute('UPDATE users SET trust = trust + 1 WHERE uid = ?', (uid,)); conn.commit(); conn.close()
        honor = "Ваше Величество" if donated >= 1000 else name
        await bot.send_chat_action(m.chat.id, "typing")
        await m.answer(await ask_knight_ai(uid, m.text, honor))
        
    elif "отправить" in txt:
        nums = re.findall(r'\d+', m.text)
        amt = int(nums[0]) if nums else 100
        try:
            # ИСПРАВЛЕНО: Payload теперь не пустой, а currency "XTR"
            await bot.send_invoice(
                m.chat.id, "Дар Рыцарю", f"Подношение в {amt} ⭐", "stars_payload", "", "XTR", 
                [LabeledPrice(label="⭐", amount=amt)]
            )
        except Exception as e:
            await m.answer(f"⚠️ Ошибка: {e}\n\nПроверь @BotFather!")

# --- ПЛАТЕЖИ ---
@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery): await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.successful_payment)
async def success_payment(m: types.Message):
    amt = m.successful_payment.total_amount
    conn = sqlite3.connect('bot_data.db'); conn.execute('UPDATE users SET donated = donated + ?, trust = trust + ? WHERE uid = ?', (amt, amt*5, m.from_user.id)); conn.commit(); conn.close()
    await m.answer("💖 **Твой благородный дар принят!**")

async def main():
    init_db(); await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
