import asyncio, sqlite3, logging, re, aiohttp, json, random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardButton, Message

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8418801272:AAG6KY8oRSdemGXhERo1vndcZTPdBvhUMLY'
ADMIN_ID = 7146168875             
SUPPORT_GROUP_ID = -1003587677334  
CHAT_GROUP_ID = -1003519194282     
GOLD_THRESHOLD = 1000              

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- 10 УРОВНЕЙ ДОВЕРИЯ ---
TRUST_LEVELS = {
    0: "Незнакомец 🌫", 10: "Прохожий 👣", 30: "Знакомый 👋", 
    60: "Собеседник 🗣", 100: "Приятель 🤝", 200: "Напарник ⚔️", 
    400: "Друг ✨", 700: "Близкий друг ❤️", 1200: "Родная душа ♾", 
    2000: "Пламя сердца 🔥"
}

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                 (uid INTEGER PRIMARY KEY, name TEXT, trust INTEGER DEFAULT 0, 
                  donated INTEGER DEFAULT 0, last_mission TEXT, mission_streak INTEGER DEFAULT 0,
                  achievements TEXT DEFAULT '[]')''')
    cursor.execute('CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, role TEXT, content TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS mood_diary (uid INTEGER, date TEXT, emotion TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    conn.commit()
    conn.close()

def get_user(uid):
    conn = sqlite3.connect('bot_data.db')
    res = conn.execute('SELECT name, trust, donated, mission_streak, achievements, last_mission FROM users WHERE uid = ?', (uid,)).fetchone()
    conn.close()
    return res

def update_db(query, params):
    conn = sqlite3.connect('bot_data.db')
    conn.execute(query, params); conn.commit(); conn.close()

# --- АЧИВКИ ---
async def add_achievement(uid, name, trust_bonus=0):
    u = get_user(uid)
    if not u: return
    achs = json.loads(u[4])
    if name not in achs:
        achs.append(name)
        update_db('UPDATE users SET achievements = ?, trust = trust + ? WHERE uid = ?', (json.dumps(achs), trust_bonus, uid))
        await bot.send_message(uid, f"🏆 **НОВОЕ ДОСТИЖЕНИЕ:** {name}!\n+{trust_bonus} к доверию.")

# --- ИНТЕЛЛЕКТ (СТРОГО БЕЗ АНГЛИЙСКОГО) ---
async def ask_knight_ai(uid, text, honor_name, trust_rank):
    conn = sqlite3.connect('bot_data.db')
    conn.execute('INSERT INTO memory (uid, role, content) VALUES (?, ?, ?)', (uid, "user", text))
    conn.commit()
    sys_prompt = f"Ты — Потерянный рыцарь. Твой господин — {honor_name}. Ранг: {trust_rank}. ОТВЕЧАЙ СТРОГО НА РУССКОМ. Никакой латиницы."
    history = [{"role": "system", "content": sys_prompt}]
    rows = conn.execute('SELECT role, content FROM memory WHERE uid = ? ORDER BY id DESC LIMIT 10', (uid,)).fetchall()
    conn.close()
    for r in reversed(rows): history.append({"role": r[0], "content": r[1]})
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.pawan.krd/cosmosrp/v1/chat/completions", 
                                   json={"model": "gpt-3.5-turbo", "messages": history}, timeout=25) as resp:
                data = await resp.json()
                reply = data['choices'][0]['message']['content']
                update_db('INSERT INTO memory (uid, role, content) VALUES (?, ?, ?)', (uid, "assistant", reply))
                return reply
    except: return "Я рядом... ❤️"

# --- КЛАВИАТУРЫ ---
def main_menu_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="☁️ Поддержка"), builder.button(text="🌸 Общение")
    builder.button(text="📖 Дневник настроения"), builder.button(text="🔥 Ежедневная миссия")
    builder.button(text="🤖 Пообщаться с ИИ")
    return builder.adjust(2, 2, 1).as_markup(resize_keyboard=True)

def back_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Назад в меню")
    return builder.as_markup(resize_keyboard=True)

user_modes = {}

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(m: Message):
    init_db()
    update_db('INSERT OR IGNORE INTO users (uid, name) VALUES (?, ?)', (m.from_user.id, m.from_user.first_name))
    await m.answer(f"Здравствуй, {m.from_user.first_name}! 🛡️", reply_markup=main_menu_kb())

@dp.message(Command("status"))
async def cmd_status(m: Message):
    u = get_user(m.from_user.id)
    if not u: return
    rank = next((v for k, v in sorted(TRUST_LEVELS.items(), reverse=True) if u[1] >= k), "Незнакомец")
    streak_fire = "🔥" * (min(u[3], 7))
    achs = ", ".join(json.loads(u[4])) if u[4] != '[]' else "Нет"
    text = (f"📊 **СТАТУС:**\n👤 Имя: {u[0]}\n🆙 Ранг: {rank}\n📈 Доверие: {u[1]}\n"
            f"{streak_fire} Серия миссий: {u[3]} дн.\n🏆 Ачивки: {achs}\n💎 Скин: {'Золотой' if u[2] >= GOLD_THRESHOLD else 'Обычный'}")
    await m.answer(text, parse_mode="Markdown")

@dp.message(Command("secret"))
async def cmd_secret(m: Message):
    await m.answer("🕵️ Ты нашел секретную команду! Доверие +50.")
    await add_achievement(m.from_user.id, "Исследователь", 50)

@dp.message(Command("mood"))
async def cmd_mood(m: Message):
    conn = sqlite3.connect('bot_data.db')
    rows = conn.execute('SELECT emotion, COUNT(*) FROM mood_diary WHERE uid = ? GROUP BY emotion', (m.from_user.id,)).fetchall()
    conn.close()
    if not rows: return await m.answer("Дневник пуст. ✨")
    res = "📊 **ТВОИ ЭМОЦИИ:**\n"
    for emo, count in rows: res += f"• {emo.capitalize()}: {count} раз\n"
    await m.answer(res)

# --- ЛОГИКА ГРУПП (КОПИРОВАНИЕ ИЗ ЧАТА) ---
@dp.message(F.chat.id == CHAT_GROUP_ID)
async def chat_group_relay(m: Message):
    for uid, mode in user_modes.items():
        if mode == "chat":
            try: await bot.copy_message(chat_id=uid, from_chat_id=m.chat.id, message_id=m.message_id)
            except: pass

@dp.message(F.reply_to_message & (F.chat.id == SUPPORT_GROUP_ID))
async def admin_reply(m: Message):
    if m.reply_to_message.forward_from:
        await bot.send_message(m.reply_to_message.forward_from.id, f"🛡️ **Ответ Хранителя:**\n\n{m.text}")
        await m.answer("✅ Доставлено.")

# --- ГЛАВНЫЙ ОБРАБОТЧИК ---
@dp.message()
async def main_handler(m: Message):
    if not m.text or m.text.startswith("/"): return
    uid = m.from_user.id
    txt = m.text.lower()

    # SOS
    if any(k in txt for k in ["мне очень плохо", "хочу умереть", "я изгой"]):
        await bot.forward_message(SUPPORT_GROUP_ID, m.chat.id, m.message_id)
        return await m.answer("Я рядом... Я позвала админа. ❤️")

    # ПРОКАЧКА + ПАСХАЛКИ
    update_db('UPDATE users SET trust = trust + 1 WHERE uid = ?', (uid,))
    if 0 <= datetime.now().hour <= 5: await add_achievement(uid, "Полуночник", 40)
    if any(w in txt for w in ["спасибо", "благодарю"]): await add_achievement(uid, "Вежливый человек", 30)
    if len(m.text) > 200: await add_achievement(uid, "Перфекционист", 50)

    # РЕЖИМЫ
    if m.text == "❌ Назад в меню":
        user_modes.pop(uid, None)
        return await m.answer("Возвращаемся.", reply_markup=main_menu_kb())

    if m.text == "🔥 Ежедневная миссия":
        u = get_user(uid)
        today = datetime.now().strftime("%Y-%m-%d")
        if u[5] == today: return await m.answer("Сегодня уже выполнено! ✨")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        streak = (u[3] + 1) if u[5] == yesterday else 1
        update_db('UPDATE users SET last_mission = ?, mission_streak = ?, trust = trust + 20 WHERE uid = ?', (today, streak, uid))
        if streak >= 5: await add_achievement(uid, "Герой недели", 100)
        return await m.answer(f"⚔️ Миссия выполнена! Серия: {streak} дн. Доверие +20.")

    if m.text == "🌸 Общение":
        user_modes[uid] = "chat"
        return await m.answer("Ты в общем чате.", reply_markup=back_kb())

    if m.text == "🤖 Пообщаться с ИИ":
        user_modes[uid] = "ai"
        return await m.answer("Слушаю тебя...", reply_markup=back_kb())

    # ЛОГИКА РЕЖИМОВ
    mode = user_modes.get(uid)
    if mode == "chat":
        await bot.send_message(CHAT_GROUP_ID, f"👤 **{m.from_user.first_name}:**")
        await bot.copy_message(CHAT_GROUP_ID, m.chat.id, m.message_id)
    elif mode == "ai":
        u = get_user(uid)
        rank = next((v for k, v in sorted(TRUST_LEVELS.items(), reverse=True) if u[1] >= k), "Незнакомец")
        honor = "Ваше Величество" if u[2] >= GOLD_THRESHOLD else u[0]
        await bot.send_chat_action(m.chat.id, "typing")
        await m.answer(await ask_knight_ai(uid, m.text, honor, rank))

    # ДОНАТ
    if "отправить" in txt:
        nums = re.findall(r'\d+', m.text)
        amt = int(nums[0]) if nums else 100
        await bot.send_invoice(m.chat.id, "Дар", "Поддержка.", "pay", "XTR", [LabeledPrice(label="⭐", amount=amt)], provider_token="")

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery): await bot.answer_pre_checkout_query(q.id, ok=True)

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
