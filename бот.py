import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# --- НАСТРОЙКИ ---
API_TOKEN = '8418801272:AAG6KY8oRSdemGXhERo1vndcZTPdBvhUMLY'
GROUP_SUPPORT_ID = -1003587677334  # ID группы поддержки
GROUP_CHAT_ID = -1003519194282     # ID группы для общения

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Словарь для хранения того, куда сейчас пишет пользователь
user_sessions = {}

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "Привет! Выберите режим:\n"
        "Напиши поддержка если хочешь чтобы тебя поддержали.\n"
        "Напиши общение если хочешь просто пообщаться."
    )

@dp.message(F.text.lower() == "поддержка")
async def support_mode(message: types.Message):
    user_sessions[message.from_user.id] = GROUP_SUPPORT_ID
    await message.answer("напиши что нибудь, и админы в скором времени тебе ответят")

@dp.message(F.text.lower() == "общение")
async def chat_mode(message: types.Message):
    user_sessions[message.from_user.id] = GROUP_CHAT_ID
    await message.answer("напиши что нибудь, и админы в скором времени тебе ответят")

# Пересылка сообщения от пользователя в группу
@dp.message(F.chat.type == "private")
async def handle_private_messages(message: types.Message):
    target_group = user_sessions.get(message.from_user.id)
    
    if not target_group:
        await message.answer("Сначала выберите режим: 'поддержка' или 'общение'.")
        return

    # Пересылаем сообщение в нужную группу
    # Мы используем copy_message, чтобы бот просто дублировал текст
    sent_msg = await message.copy_to(
        chat_id=target_group,
        # В тексте добавим информацию о том, кто пишет
        caption=f"От: {message.from_user.full_name} (ID: {message.from_user.id})" if message.caption else None
    )
    
    # Если это просто текст, пометим его (опционально)
    if not message.photo and not message.document:
        await bot.send_message(target_group, f"👤 Сообщение от пользователя {message.from_user.full_name} (ID: {message.from_user.id})")

# Ответ из группы пользователю
@dp.message((F.chat.id == GROUP_SUPPORT_ID) | (F.chat.id == GROUP_CHAT_ID))
async def handle_group_reply(message: types.Message):
    # Проверяем, что сообщение является ответом на пересланное ботом сообщение
    if message.reply_to_message:
        # Пытаемся вытащить ID пользователя из текста сообщения (простой способ)
        # Или, если вы используете forward, можно достать из оригинальных данных
        # В данном примере предполагается, что админ отвечает на сообщение
        
        # ВАЖНО: Это упрощенная логика. Чтобы она работала идеально, 
        # нужно хранить связи ID сообщений в базе данных.
        pass

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
