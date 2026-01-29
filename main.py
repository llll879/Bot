import asyncio, sqlite3, logging, re, aiohttp, json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8418801272:AAG6KY8oRSdemGXhERo1vndcZTPdBvhUMLY'
ADMIN_ID = 7146168875            # Ваш ID
SUPPORT_GROUP_ID = -1003587677334  # ID группы поддержки
CHAT_GROUP_ID = -1003519194282     # ID группы общения

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Ранги доверия
TRUST_LEVELS = {
    0: "Странник 🌫",
    30: "Собеседник 🗣",
    100: "Приятель 🤝",
    210: "Близкий друг ❤️",
    500: "Вечный спутник ♾"
}

# --- РАБОТА С БАЗОЙ ДАННЫХ (ВЕЧНАЯ ПАМЯТЬ) ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    # Таблица пользователей
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                 (uid INTEGER PRIMARY KEY, name TEXT, trust INTEGER DEFAULT 0, donated INTEGER DEFAULT 0)''')
    # Таблица вечной памяти диалогов
    conn.execute('''CREATE TABLE IF NOT EXISTS memory 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, role TEXT, content TEXT)''')
    conn.commit()
    conn.close()

def save_to_memory(uid, role, content):
    conn = sqlite3.connect('bot_data.db')
    conn.execute('INSERT INTO memory (uid, role, content) VALUES (?, ?, ?)', (uid, role, content))
    # Ограничиваем историю 30 сообщениями для стабильности ИИ
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
    # Сохраняем текущее сообщение пользователя в вечную память
    save_to_memory(uid, "user", text)
    
    # Собираем контекст: системная роль + история из БД
    history = [
        {"role": "system", "content": f"Ты преданный Рыцарь сердца. Твой господин — {honor_name}. Отвечай ласково, преданно и используй знания из прошлых бесед."}
    ]
    history.extend(get_history(uid))

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": history
            }
            async with session.post("https://api.pawan.krd/cosmosrp/v1/chat/completions", json=payload, timeout=15) as resp:
                data = await resp.json()
                reply = data['choices'][0]['message']['content']
                # Сохраняем ответ ИИ в вечную память
                save_to_memory(uid, "assistant", reply)
                return reply
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return f"Радость моя {honor_name}, я на мгновение погрузился в свои думы о тебе... Повтори, пожалуйста! ❤️"

# --- КЛАВИАТУРЫ ---
def main_menu_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="☁️ Поддержка")
    builder.button(text="🌸 Общение")
    builder.button(text="🤖 Пообщаться с ИИ")
    return builder.adjust(2, 1).as_markup(resize_keyboard=True)

def back_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Назад в меню")
    return builder.as_markup(resize_keyboard=True)

user_modes = {}

# --- КОМАНДЫ АДМИНИСТРАТОРА ---
@dp.message(Command("send"))
async def admin_broadcast(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ У вас нет прав правителя.")
    
    broadcast_text = command.args
    if not broadcast_text:
        return await message.answer("⚠️ Пишите: `/send [текст]`", parse_mode="Markdown")

    conn = sqlite3.connect('bot_data.db')
    users = conn.execute('SELECT uid FROM users').fetchall()
    conn.close()

    count, blocked = 0, 0
    status_msg = await message.answer(f"🚀 Начинаю рассылку на {len(users)} душ...")

    for user in users:
        try:
            await bot.send_message(user[0], broadcast_text)
            count += 1
            await asyncio.sleep(0.05)
        except:
            blocked += 1
    
    await status_msg.edit_text(f"✅ Рассылка завершена!\n👤 Получили: {count}\n🚫 Заблокировали: {blocked}")

# --- БАЗОВЫЕ КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    init_db()
    conn = sqlite3.connect('bot_data.db')
    conn.execute('INSERT OR IGNORE INTO users (uid, name) VALUES (?, ?)', (m.from_user.id, m.from_user.first_name))
    conn.commit()
    conn.close()
    await m.answer(
        f"Здравствуй! Я твой Рыцарь сердца. ❤️🛡️\n"
        f"Моя память теперь вечна, а преданность бесконечна.\n\n"
        f"Используй /help, чтобы увидеть мои возможности.",
        reply_markup=main_menu_kb()
    )

@dp.message(Command("help"))
async def cmd_help(m: types.Message):
    help_text = (
        "📜 **ГРАМОТА ВЕРНОГО РЫЦАРЯ**\n━━━━━━━━━━━━━━━━━━━━\n"
        "✨ **КОМАНДЫ:**\n"
        "• `/status` — Твой ранг и уровень доверия.\n"
        "• `/top` — Список самых щедрых меценатов.\n"
        "• `/start` — Перезапустить меню.\n\n"
        "🎮 **КНОПКИ:**\n"
        "• **☁️ Поддержка** — Отправляет экстренный **SOS-сигнал** админам.\n"
        "• **🌸 Общение** — Пересылает твои слова в общую залу чата.\n"
        "• **🤖 Пообщаться с ИИ** — Личный диалог с **вечной памятью**.\n\n"
        "💎 **БЛАГОРОДСТВО:**\n"
        "• Напиши `отправить 100`, чтобы принести дар (⭐).\n"
        "• Дар от **1000 ⭐** открывает **Золотой скин** и титул 'Ваше Величество'! 👑"
    )
    await m.answer(help_text, parse_mode="Markdown")

@dp.message(Command("status"))
async def cmd_status(m: types.Message):
    name, trust, donated = get_user(m.from_user.id)
    rank = next((v for k, v in sorted(TRUST_LEVELS.items(), reverse=True) if trust >= k), "Странник 🌫")
    skin = "🟡 ЗОЛОТОЙ СКИН 👑" if donated >= 1000 else "⚪ Обычный путник"
    await m.answer(
        f"📊 **ТВОЙ СТАТУС**\n━━━━━━━━━━━━━━\n"
        f"👤 Имя: {name}\n"
        f"🆙 Ранг: {rank}\n"
        f"📈 Доверие: {trust}\n"
        f"💎 Скин: {skin}"
    )

@dp.message(Command("top"))
async def cmd_top(m: types.Message):
    conn = sqlite3.connect('bot_data.db')
    rows = conn.execute('SELECT name, donated FROM users WHERE donated > 0 ORDER BY donated DESC LIMIT 10').fetchall()
    conn.close()
    if not rows:
        return await m.answer("Список героев пока пуст... 🌸")
    
    res = "🏆 **ГЕРОИ КОРОЛЕВСТВА**\n\n"
    for i, (name, amt) in enumerate(rows, 1):
        icon = "👑" if amt >= 1000 else "👤"
        res += f"{i}. {icon} {name} — {amt} ⭐\n"
    await m.answer(res)

# --- ОБРАБОТКА ВСЕХ СООБЩЕНИЙ ---
@dp.message()
async def main_handler(m: types.Message):
    if not m.text or m.text.startswith("/"): return
    uid = m.from_user.id

    # 1. Ответ админа из группы (Reply)
    if m.chat.type in ['group', 'supergroup'] and m.reply_to_message:
        if m.reply_to_message.forward_from:
            try:
                await bot.send_message(m.reply_to_message.forward_from.id, f"<b>📩 Ответ от Рыцаря:</b>\n\n{m.text}", parse_mode="HTML")
                await m.reply("✅ Ответ доставлен!")
            except:
                await m.reply("❌ Не удалось отправить (пользователь закрыл личку).")
        return

    # 2. Логика кнопок переключения режимов
    if m.text == "☁️ Поддержка":
        user_modes[uid] = "support"
        return await m.answer("🆘 **SOS РЕЖИМ АКТИВИРОВАН**\nНапиши свой вопрос, и я мгновенно передам его админам!", reply_markup=back_kb())
    
    if m.text == "🌸 Общение":
        user_modes[uid] = "chat"
        return await m.answer("Напиши сообщение, и я перешлю его в общий чат:", reply_markup=back_kb())
    
    if m.text == "🤖 Пообщаться с ИИ":
        user_modes[uid] = "ai"
        return await m.answer("Я слушаю тебя, радость моя... Я помню каждое наше слово. 🥰", reply_markup=back_kb())
    
    if m.text == "❌ Назад в меню":
        user_modes.pop(uid, None)
        return await m.answer("Возвращаюсь на пост!", reply_markup=main_menu_kb())

    # 3. Работа активных режимов
    mode = user_modes.get(uid)
    
    if mode == "support":
        # Пересылка SOS сообщения
        await bot.send_message(SUPPORT_GROUP_ID, f"🚨 **SOS СИГНАЛ** от @{m.from_user.username or uid}:")
        await bot.forward_message(SUPPORT_GROUP_ID, m.chat.id, m.message_id)
        await m.answer("🚀 Твой сигнал SOS доставлен админам! Ожидай ответа.")
        
    elif mode == "chat":
        # Пересылка в группу общения
        await bot.forward_message(CHAT_GROUP_ID, m.chat.id, m.message_id)
        await m.answer("🌸 Твое послание улетело в общий чат!")
        
    elif mode == "ai":
        # Логика ИИ с вечной памятью
        name, trust, donated = get_user(uid)
        # Прокачка доверия за общение
        conn = sqlite3.connect('bot_data.db')
        conn.execute('UPDATE users SET trust = trust + 1 WHERE uid = ?', (uid,))
        conn.commit()
        conn.close()
        
        honor = "Ваше Величество" if donated >= 1000 else name
        await bot.send_chat_action(m.chat.id, "typing")
        
        response = await ask_knight_ai(uid, m.text, honor)
        await m.answer(response)
    
    # 4. Донаты через текст "отправить [число]"
    elif "отправить" in m.text.lower():
        nums = re.findall(r'\d+', m.text)
        amt = int(nums[0]) if nums else 100
        try:
            await bot.send_invoice(
                m.chat.id, "Дар Рыцарю", f"Пожертвование {amt} ⭐", "pay", "", "XTR", 
                [LabeledPrice(label="⭐", amount=amt)]
            )
        except:
            await m.answer("⚠️ Пожалуйста, включите Telegram Stars в @BotFather! ❤️")
    
    else:
        await m.answer("Солнышко, выберите режим на кнопках ниже! 👇", reply_markup=main_menu_kb())

# --- ОБРАБОТКА ПЛАТЕЖЕЙ ---
@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.successful_payment)
async def success_payment(m: types.Message):
    amt = m.successful_payment.total_amount
    conn = sqlite3.connect('bot_data.db')
    # За донат даем много доверия (сумма * 5)
    conn.execute('UPDATE users SET donated = donated + ?, trust = trust + ? WHERE uid = ?', (amt, amt*5, m.from_user.id))
    conn.commit()
    conn.close()
    await m.answer("💖 **Твой дар принят!** Ты согреваешь моё сердце и делаешь нашего Рыцаря сильнее!")

# --- ЗАПУСК БОТА ---
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Рыцарь ушел на покой...")
