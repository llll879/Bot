import asyncio, sqlite3, logging, re, aiohttp, json, random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyParameters
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8418801272:AAG6KY8oRSdemGXhERo1vndcZTPdBvhUMLY'
ADMIN_ID = 7146168875             
SUPPORT_GROUP_ID = -1003587677334  
CHAT_GROUP_ID = -1003519194282     
GOLD_THRESHOLD = 1000              

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)

# --- СОСТОЯНИЯ FSM ---
class Form(StatesGroup):
    waiting_for_reply = State()
    waiting_for_broadcast = State()

# --- ПЕРЕМЕННЫЕ СОСТОЯНИЙ ---
user_modes = {}
message_store = {}
broadcast_cache = {}

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                 (uid INTEGER PRIMARY KEY, name TEXT, trust INTEGER DEFAULT 0, 
                  donated INTEGER DEFAULT 0, last_mission TEXT, mission_streak INTEGER DEFAULT 0,
                  achievements TEXT DEFAULT '[]', subscribed INTEGER DEFAULT 1)''')
    cursor.execute('CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, role TEXT, content TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS broadcasts (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, text TEXT, sent_at TIMESTAMP, users_count INTEGER)')
    conn.commit()
    conn.close()

def get_user(uid):
    conn = sqlite3.connect('bot_data.db')
    res = conn.execute('SELECT name, trust, donated, mission_streak, achievements, last_mission, subscribed FROM users WHERE uid = ?', (uid,)).fetchone()
    conn.close()
    return res

def get_all_users():
    conn = sqlite3.connect('bot_data.db')
    users = conn.execute('SELECT uid, name FROM users').fetchall()
    conn.close()
    return users

def get_subscribed_users():
    conn = sqlite3.connect('bot_data.db')
    users = conn.execute('SELECT uid, name FROM users WHERE subscribed = 1').fetchall()
    conn.close()
    return users

def get_users_count():
    conn = sqlite3.connect('bot_data.db')
    count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    conn.close()
    return count

def update_db(query, params):
    conn = sqlite3.connect('bot_data.db')
    conn.execute(query, params); conn.commit(); conn.close()

# --- АДМИН ПАНЕЛЬ ---
@dp.message(Command("admin"))
async def admin_panel(m: Message):
    if m.from_user.id != ADMIN_ID:
        await m.answer("⛔ Доступ запрещен")
        return
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📊 Статистика", callback_data="admin_stats")
    keyboard.button(text="📢 Сделать рассылку", callback_data="admin_broadcast")
    keyboard.button(text="👥 Управление подписками", callback_data="admin_subscriptions")
    keyboard.button(text="📜 История рассылок", callback_data="admin_broadcast_history")
    keyboard.adjust(1)
    
    await m.answer(
        "🛡️ **Панель администратора**\n\n"
        "Выберите действие:",
        reply_markup=keyboard.as_markup()
    )

# --- ОБРАБОТЧИКИ АДМИН КНОПОК ---
@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    users_count = get_users_count()
    subscribed = get_subscribed_users()
    subscribed_count = len(subscribed)
    
    stats_text = f"""
📊 **Статистика бота:**

👥 Всего пользователей: {users_count}
✅ Подписаны на рассылку: {subscribed_count}
📈 Охват: {(subscribed_count/users_count*100) if users_count > 0 else 0:.1f}%

⚡ Активных сейчас: {len(user_modes)}
"""
    
    await callback.message.edit_text(stats_text)
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📢 **Создание рассылки**\n\n"
        "Отправьте сообщение для рассылки (текст, фото, видео и т.д.):\n"
        "Или отправьте /cancel для отмены"
    )
    await state.set_state(Form.waiting_for_broadcast)
    await callback.answer()

@dp.callback_query(F.data == "admin_subscriptions")
async def admin_subscriptions(callback: CallbackQuery):
    subscribed = get_subscribed_users()
    total = get_users_count()
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📥 Включить всем подписку", callback_data="admin_subscribe_all")
    keyboard.button(text="📤 Отключить всем подписку", callback_data="admin_unsubscribe_all")
    keyboard.button(text="◀️ Назад", callback_data="admin_back")
    keyboard.adjust(1)
    
    await callback.message.edit_text(
        f"👥 **Управление подписками**\n\n"
        f"Всего пользователей: {total}\n"
        f"Подписаны: {len(subscribed)}\n"
        f"Не подписаны: {total - len(subscribed)}",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast_history")
async def admin_broadcast_history(callback: CallbackQuery):
    conn = sqlite3.connect('bot_data.db')
    broadcasts = conn.execute(
        "SELECT admin_id, text, sent_at, users_count FROM broadcasts ORDER BY id DESC LIMIT 10"
    ).fetchall()
    conn.close()
    
    if not broadcasts:
        history_text = "📜 История пуста"
    else:
        history_text = "📜 **Последние 10 рассылок:**\n\n"
        for i, (admin_id, text, sent_at, users_count) in enumerate(broadcasts, 1):
            preview = (text[:50] + "...") if text and len(text) > 50 else (text or "Медиа сообщение")
            history_text += f"{i}. 📨 {preview}\n"
            history_text += f"   👥 Получили: {users_count}\n"
            history_text += f"   ⏰ {sent_at}\n\n"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="◀️ Назад", callback_data="admin_back")
    
    await callback.message.edit_text(history_text, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "admin_subscribe_all")
async def admin_subscribe_all(callback: CallbackQuery):
    conn = sqlite3.connect('bot_data.db')
    conn.execute("UPDATE users SET subscribed = 1")
    conn.commit()
    conn.close()
    
    await callback.answer("✅ Все пользователи подписаны на рассылку")
    await admin_subscriptions(callback)

@dp.callback_query(F.data == "admin_unsubscribe_all")
async def admin_unsubscribe_all(callback: CallbackQuery):
    conn = sqlite3.connect('bot_data.db')
    conn.execute("UPDATE users SET subscribed = 0")
    conn.commit()
    conn.close()
    
    await callback.answer("✅ Подписка отключена у всех пользователей")
    await admin_subscriptions(callback)

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    await admin_panel(callback.message)
    await callback.answer()

# --- ОБРАБОТКА СООБЩЕНИЯ ДЛЯ РАССЫЛКИ ---
@dp.message(Form.waiting_for_broadcast)
async def process_broadcast_message(m: Message, state: FSMContext):
    if m.text and m.text.lower() in ["/cancel", "отмена"]:
        await state.clear()
        await m.answer("❌ Рассылка отменена")
        return
    
    users = get_subscribed_users()
    
    if not users:
        await m.answer("❌ Нет подписанных пользователей для рассылки")
        await state.clear()
        return
    
    user_id = m.from_user.id
    broadcast_cache[user_id] = {
        "message": m,
        "users": users,
        "message_type": "text",
        "file_id": None,
        "caption": None
    }
    
    if m.text:
        broadcast_cache[user_id]["message_type"] = "text"
        preview_text = m.text[:200] + "..." if len(m.text) > 200 else m.text
    elif m.photo:
        broadcast_cache[user_id]["message_type"] = "photo"
        broadcast_cache[user_id]["file_id"] = m.photo[-1].file_id
        broadcast_cache[user_id]["caption"] = m.caption
        preview_text = f"Фото + текст: {m.caption[:100] if m.caption else 'Без текста'}"
    elif m.video:
        broadcast_cache[user_id]["message_type"] = "video"
        broadcast_cache[user_id]["file_id"] = m.video.file_id
        broadcast_cache[user_id]["caption"] = m.caption
        preview_text = f"Видео + текст: {m.caption[:100] if m.caption else 'Без текста'}"
    elif m.document:
        broadcast_cache[user_id]["message_type"] = "document"
        broadcast_cache[user_id]["file_id"] = m.document.file_id
        broadcast_cache[user_id]["caption"] = m.caption
        preview_text = f"Документ + текст: {m.caption[:100] if m.caption else 'Без текста'}"
    else:
        broadcast_cache[user_id]["message_type"] = "forward"
        preview_text = "Сообщение с медиа"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Отправить рассылку", callback_data="confirm_broadcast")
    keyboard.button(text="❌ Отменить", callback_data="cancel_broadcast")
    
    await m.answer(
        f"📢 **Подтверждение рассылки**\n\n"
        f"📝 Тип: {broadcast_cache[user_id]['message_type']}\n"
        f"👥 Получателей: {len(users)}\n"
        f"📄 Содержимое: {preview_text}\n\n"
        f"Отправить рассылку?",
        reply_markup=keyboard.as_markup()
    )

# --- ПОДТВЕРЖДЕНИЕ РАССЫЛКИ ---
@dp.callback_query(F.data == "confirm_broadcast")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if user_id not in broadcast_cache:
        await callback.answer("❌ Данные рассылки устарели. Начните заново.")
        await state.clear()
        return
    
    data = broadcast_cache[user_id]
    users = data["users"]
    message_type = data["message_type"]
    
    await callback.message.edit_text("🔄 Начинаю рассылку...")
    
    success_count = 0
    fail_count = 0
    failed_users = []
    
    for uid, name in users:
        try:
            if message_type == "text":
                await bot.send_message(uid, data["message"].text)
            elif message_type == "photo":
                await bot.send_photo(uid, data["file_id"], caption=data["caption"])
            elif message_type == "video":
                await bot.send_video(uid, data["file_id"], caption=data["caption"])
            elif message_type == "document":
                await bot.send_document(uid, data["file_id"], caption=data["caption"])
            elif message_type == "forward":
                await bot.copy_message(uid, data["message"].chat.id, data["message"].message_id)
            
            success_count += 1
            if success_count % 20 == 0:
                await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(0.05)
                
        except Exception as e:
            logging.error(f"Failed to send to {uid} ({name}): {e}")
            fail_count += 1
            failed_users.append(f"{name} (ID: {uid})")
    
    text_content = ""
    if data["message"].text:
        text_content = data["message"].text
    elif data["caption"]:
        text_content = data["caption"]
    elif data["message_type"] != "text":
        text_content = f"{data['message_type'].capitalize()} сообщение"
    
    conn = sqlite3.connect('bot_data.db')
    conn.execute(
        "INSERT INTO broadcasts (admin_id, text, sent_at, users_count) VALUES (?, ?, ?, ?)",
        (user_id, text_content[:1000], 
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), success_count)
    )
    conn.commit()
    conn.close()
    
    if user_id in broadcast_cache:
        del broadcast_cache[user_id]
    await state.clear()
    
    report_text = f"✅ **Рассылка завершена!**\n\n"
    report_text += f"📊 Статистика:\n"
    report_text += f"• 👥 Всего получателей: {len(users)}\n"
    report_text += f"• ✅ Успешно отправлено: {success_count}\n"
    report_text += f"• ❌ Не удалось отправить: {fail_count}\n"
    report_text += f"• 📈 Успешность: {(success_count/len(users)*100) if users else 0:.1f}%\n"
    
    if failed_users and len(failed_users) <= 10:
        report_text += f"\n❌ Не отправлено пользователям:\n"
        for user in failed_users[:10]:
            report_text += f"• {user}\n"
    
    await callback.message.edit_text(report_text)
    await callback.answer()

@dp.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id in broadcast_cache:
        del broadcast_cache[user_id]
    
    await state.clear()
    await callback.message.edit_text("❌ Рассылка отменена")
    await callback.answer()

# --- КОМАНДА ДЛЯ ПОЛЬЗОВАТЕЛЕЙ: УПРАВЛЕНИЕ ПОДПИСКОЙ ---
@dp.message(Command("subscribe"))
async def user_subscribe(m: Message):
    conn = sqlite3.connect('bot_data.db')
    
    user = conn.execute('SELECT subscribed FROM users WHERE uid = ?', (m.from_user.id,)).fetchone()
    
    if not user:
        conn.execute(
            'INSERT INTO users (uid, name, trust, subscribed) VALUES (?, ?, 1, 1)',
            (m.from_user.id, m.from_user.first_name or "Путник")
        )
        subscribed = 1
    else:
        new_status = 0 if user[0] else 1
        conn.execute('UPDATE users SET subscribed = ? WHERE uid = ?', (new_status, m.from_user.id))
        subscribed = new_status
    
    conn.commit()
    conn.close()
    
    if subscribed:
        await m.answer("✅ Вы подписались на рассылку! Буду присылать важные объявления.")
    else:
        await m.answer("❌ Вы отписались от рассылки. Вы не будете получать объявления.")

# --- КОМАНДА HELP ---
@dp.message(Command("help"))
async def cmd_help(m: Message):
    help_text = """
🏰 **Помощь по боту Древний Замок**

**Основные команды:**
/start - Начать работу с ботом
/help - Показать это сообщение
/subscribe - Управление подпиской на рассылку

**Режимы работы:**
🌸 Общение - Вход в общий чат с другими путниками
🤖 Пообщаться с ИИ - Беседа с Хранителем замка
🔥 Ежедневная миссия - Выполнение заданий
📊 Моя статистика - Просмотр вашего прогресса
☁️ Поддержка - Связь с Хранителями

**Как общаться:**
- В общем чате: пишите сообщения, их увидят все
- С ИИ: ведите естественный диалог
- Для экстренной помощи: напишите "мне плохо"

**Ответы на сообщения:**
Вы можете отвечать на сообщения в ЛС свайпом влево (Reply)

Всегда ваш, Хранитель Древнего Замка 🏰
"""
    await m.answer(help_text, reply_markup=main_menu_kb() if m.chat.type == "private" else None)

# --- ИИ ПРОМПТ (СТАРЫЙ ВАРИАНТ) ---
async def ai_response(text: str, uid: int) -> str:
    """Генерация ответа ИИ с естественным диалогом"""
    try:
        conn = sqlite3.connect('bot_data.db')
        history = conn.execute(
            "SELECT role, content FROM memory WHERE uid = ? ORDER BY id DESC LIMIT 5",
            (uid,)
        ).fetchall()
        conn.close()
        
        context = ""
        for role, content in reversed(history):
            context += f"{role}: {content}\n"
        
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["привет", "здравствуй", "добрый", "хай", "hello"]):
            responses = [
                "Приветствую, путник. Что привело тебя в эти древние стены?",
                "Здравствуй. Я чувствую, у тебя есть что рассказать.",
                "Привет. Замок сегодня тих, только эхо наших слов бродит по коридорам."
            ]
        
        elif any(word in text_lower for word in ["как дела", "как ты", "самочувствие", "настроение"]):
            responses = [
                "Духи замка спокойны сегодня. А как твои дела, путник?",
                "Всё как всегда: тишина, эхо и тайны. А ты как?",
                "Слушаю шепот древних стен. Расскажи, что у тебя нового?"
            ]
        
        elif any(word in text_lower for word in ["замок", "стены", "тайны", "древн"]):
            responses = [
                "Этот замок помнит много историй. Есть ли у тебя своя?",
                "Стены здесь хранят секреты. Что тебя интересует больше всего?",
                "Каждая комната здесь имеет свою душу. Хочешь узнать одну из тайн?"
            ]
        
        elif any(word in text_lower for word in ["кто ты", "твоё имя", "хранитель"]):
            responses = [
                "Я - эхо этого замка, его память и его голос. А ты кто в этой истории?",
                "Меня зовут Хранитель. Я здесь столько, сколько помнят эти камни. А ты?",
                "Я просто проводник между мирами. А что для тебя значит имя?"
            ]
        
        elif any(word in text_lower for word in ["пока", "до свидан", "прощай", "ухожу"]):
            responses = [
                "До встречи, путник. Замок всегда будет ждать твоего возвращения.",
                "Прощай. Пусть твоя дорога будет светлой.",
                "Возвращайся, когда захочешь поговорить. Я буду здесь."
            ]
        
        else:
            responses = [
                f"Интересно... {text} Расскажи об этом подробнее?",
                f"Я понял тебя. {text} А что ты сам об этом думаешь?",
                f"{text} Задумывался ли ты, что это значит для тебя?",
                "Хм... А как ты пришел к этой мысли?",
                "Понятно. А что чувствуешь, говоря об этом?",
                "Интересная мысль. Что натолкнуло тебя на это?",
                "Расскажи больше, мне интересно твое мнение.",
                "А как это связано с твоей жизнью?",
                "Что для тебя самое важное в этом?"
            ]
        
        response = random.choice(responses)
        
        conn = sqlite3.connect('bot_data.db')
        conn.execute("INSERT INTO memory (uid, role, content) VALUES (?, 'user', ?)", (uid, text))
        conn.execute("INSERT INTO memory (uid, role, content) VALUES (?, 'assistant', ?)", (uid, response))
        conn.commit()
        conn.close()
        
        return response
        
    except Exception as e:
        logging.error(f"AI error: {e}")
        return "Духи замка задумались... Попробуй сказать иначе."

# --- ОБРАБОТЧИК ОТВЕТОВ НА СООБЩЕНИЯ (Reply/swipe) ---
@dp.message(F.reply_to_message)
async def handle_reply_message(m: Message):
    """Обработка ответов через свайп/Reply"""
    try:
        replied_msg = m.reply_to_message
        
        # Если ответ на сообщение в ЛС (от бота)
        if m.chat.type == "private" and replied_msg.from_user.id == bot.id:
            # Ищем оригинальное сообщение в message_store
            for msg_id, msg_info in message_store.items():
                # Проверяем по тексту или ID
                if (replied_msg.text and msg_info.get("text") in replied_msg.text) or \
                   (replied_msg.caption and msg_info.get("text") in replied_msg.caption):
                    
                    target_uid = msg_info["uid"]
                    sender_name = m.from_user.first_name or "Аноним"
                    
                    # Отправляем ответ пользователю
                    await bot.send_message(
                        target_uid,
                        f"💌 **Ответ от {sender_name}:**\n\n{m.text or m.caption or '...'}",
                        reply_markup=back_kb()
                    )
                    
                    # Подтверждение отправителю
                    await m.answer("✅ Ответ отправлен!")
                    return
        
        # Если ответ в группе поддержки (сообщения НЕ удаляются)
        elif m.chat.id == SUPPORT_GROUP_ID and replied_msg.forward_from:
            target_uid = replied_msg.forward_from.id
            await bot.send_message(
                target_uid,
                f"🛡️ **Ответ Хранителя:**\n\n{m.text}",
                reply_markup=back_kb()
            )
            # СООБЩЕНИЯ НЕ УДАЛЯЮТСЯ ИЗ ГРУППЫ
            await m.answer("✅ Ответ доставлен пользователю.")
            return
            
        # Если ответ в общем чате
        elif m.chat.id == CHAT_GROUP_ID:
            # Сохраняем для возможности ответа
            message_store[m.message_id] = {
                "uid": m.from_user.id,
                "name": m.from_user.first_name,
                "text": m.text if m.text else "Сообщение"
            }
            
            # Пересылаем в ЛС тем, кто в режиме чата
            for uid, mode in user_modes.items():
                if mode == "chat":
                    try:
                        author = m.from_user.first_name if m.from_user else "Путник"
                        # Отправляем как ответ если есть reply_to_message
                        if replied_msg:
                            reply_author = replied_msg.from_user.first_name if replied_msg.from_user else "Кто-то"
                            reply_text = replied_msg.text or replied_msg.caption or "..."
                            reply_preview = reply_text[:50] + "..." if len(reply_text) > 50 else reply_text
                            
                            await bot.send_message(
                                uid,
                                f"💬 **{author}** → **{reply_author}**:\n"
                                f"📝 {reply_preview}\n\n"
                                f"💭 {m.text or '...'}"
                            )
                        else:
                            await bot.send_message(uid, f"👤 **{author}:**\n{m.text or '...'}")
                    except:
                        pass
            return
            
    except Exception as e:
        logging.error(f"Reply error: {e}")

# --- ЛОГИКА ГРУПП ---
@dp.message(F.chat.id == CHAT_GROUP_ID)
async def chat_group_relay(m: Message):
    # Сохраняем сообщение
    if m.from_user:
        message_store[m.message_id] = {
            "uid": m.from_user.id,
            "name": m.from_user.first_name,
            "text": m.text if m.text else "Сообщение"
        }
    
    # Ретрансляция в ЛС
    for uid, mode in user_modes.items():
        if mode == "chat":
            try:
                author = m.from_user.first_name if m.from_user else "Путник"
                await bot.send_message(uid, f"📢 **{author}:**")
                await bot.copy_message(chat_id=uid, from_chat_id=m.chat.id, message_id=m.message_id)
            except:
                pass

@dp.message(F.chat.id == SUPPORT_GROUP_ID, F.reply_to_message)
async def support_reply_handler(m: Message):
    # Обработка ответов в группе поддержки
    if m.reply_to_message.forward_from:
        target_uid = m.reply_to_message.forward_from.id
        try:
            await bot.send_message(target_uid, f"🛡️ **Ответ Хранителя:**\n\n{m.text}")
            # СООБЩЕНИЯ НЕ УДАЛЯЮТСЯ ИЗ ГРУППЫ
            await m.answer("✅ Ответ доставлен пользователю.")
        except:
            await m.answer("❌ Не удалось доставить (возможно, бот заблокирован).")

# --- ГЛАВНЫЙ ОБРАБОТЧИК ---
@dp.message()
async def main_handler(m: Message):
    if m.chat.type != "private": 
        return
    
    if not m.text:
        return
    
    uid = m.from_user.id
    txt = m.text.lower()

    # Автоматическое создание пользователя
    conn = sqlite3.connect('bot_data.db')
    user_exists = conn.execute('SELECT uid FROM users WHERE uid = ?', (uid,)).fetchone()
    if not user_exists:
        conn.execute(
            'INSERT INTO users (uid, name, trust, subscribed) VALUES (?, ?, 1, 1)',
            (uid, m.from_user.first_name or "Путник")
        )
    else:
        conn.execute('UPDATE users SET trust = trust + 1 WHERE uid = ?', (uid,))
    conn.commit()
    conn.close()

    # SOS система
    if any(k in txt for k in ["мне плохо", "хочу умереть", "я изгой"]):
        await bot.forward_message(SUPPORT_GROUP_ID, m.chat.id, m.message_id)
        return await m.answer("Я рядом... Я передала твою весть Хранителям. ❤️")

    # Кнопки меню
    if m.text == "❌ Назад в меню":
        user_modes.pop(uid, None)
        return await m.answer("Возвращаемся в замок.", reply_markup=main_menu_kb())

    if m.text == "🌸 Общение":
        user_modes[uid] = "chat"
        return await m.answer(
            "Ты вошел в общий чат. Твои слова услышат все путники.\n\n"
            "Чтобы ответить на чье-то сообщение, просто напиши в чат - оно будет переслано всем.",
            reply_markup=back_kb()
        )
    
    if m.text == "🤖 Пообщаться с ИИ":
        user_modes[uid] = "ai"
        return await m.answer(
            "Я здесь, путник. Говори со мной... Что на душе? 🏰",
            reply_markup=back_kb()
        )

    # Режим общения в чате
    if user_modes.get(uid) == "chat" and m.text:
        # Сохраняем сообщение
        message_store[m.message_id] = {
            "uid": uid,
            "name": m.from_user.first_name,
            "text": m.text if m.text else "Сообщение"
        }
        
        # Отправляем в группу
        await bot.send_message(CHAT_GROUP_ID, f"👤 **Послание от {m.from_user.first_name}:**")
        await bot.copy_message(CHAT_GROUP_ID, m.chat.id, m.message_id)
        
        return await m.answer("Сообщение отправлено в общий чат! ✅")

    # Режим ИИ
    if user_modes.get(uid) == "ai" and m.text:
        typing_msg = await m.answer("Духи замка задумались...")
        response = await ai_response(m.text, uid)
        await typing_msg.delete()
        await m.answer(response, reply_markup=back_kb())
        return

    # Если режим не определен, показываем меню
    if uid not in user_modes:
        await m.answer("Выбери путь, путник:", reply_markup=main_menu_kb())

# --- КОМАНДА START ---
@dp.message(Command("start"))
async def cmd_start(m: Message):
    user_modes.pop(m.from_user.id, None)
    
    conn = sqlite3.connect('bot_data.db')
    user_exists = conn.execute('SELECT uid FROM users WHERE uid = ?', (m.from_user.id,)).fetchone()
    if not user_exists:
        conn.execute(
            'INSERT INTO users (uid, name, trust, subscribed) VALUES (?, ?, 1, 1)',
            (m.from_user.id, m.from_user.first_name or "Путник")
        )
        conn.commit()
    conn.close()
    
    await m.answer(
        "Добро пожаловать в Древний Замок! 🏰\n\n"
        "Я - хранитель этих стен. Выбери, как проведешь время здесь:\n\n"
        "📢 Подписка на новости: /subscribe\n"
        "🆘 Помощь: /help",
        reply_markup=main_menu_kb()
    )

# --- СТАРОЕ МЕНЮ ---
def main_menu_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="☁️ Поддержка"), builder.button(text="🌸 Общение")
    builder.button(text="🔥 Ежедневная миссия"), builder.button(text="🤖 Пообщаться с ИИ")
    builder.button(text="📊 Моя статистика")
    return builder.adjust(2, 2, 1).as_markup(resize_keyboard=True)

def back_kb():
    return ReplyKeyboardBuilder().button(text="❌ Назад в меню").as_markup(resize_keyboard=True)

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())