import asyncio
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo


# [OUR] BASE_DIR указывает на папку japanese_sword, где лежит manage.py.
BASE_DIR = Path(__file__).resolve().parent.parent

# [OUR] ENV_FILE указывает на общий .env рядом с папкой japanese_sword.
ENV_FILE = BASE_DIR.parent / '.env'


# [OUR] Простая функция чтения .env, такая же идея, как в Django settings.py.
def load_env_file(path):
    if not path.exists():
        return

    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()

        if not line or line.startswith('#') or '=' not in line:
            continue

        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip())


# [OUR] Загружаем переменные окружения до создания Bot.
load_env_file(ENV_FILE)


# [OUR] Токен бота берем из .env, чтобы не хранить секрет в коде.
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# [OUR] URL Mini App берем из .env, потому что ngrok-ссылка временная и может меняться.
WEB_APP_URL = os.environ.get('TELEGRAM_WEB_APP_URL')


# [OUR] Если токена нет, бот не сможет подключиться к Telegram Bot API.
if not BOT_TOKEN:
    raise RuntimeError('TELEGRAM_BOT_TOKEN не задан в .env')

# [OUR] Если URL нет, кнопка не будет знать, какую Mini App открывать.
if not WEB_APP_URL:
    raise RuntimeError('TELEGRAM_WEB_APP_URL не задан в .env')


# [AIOGRAM] Bot — объект подключения к Telegram Bot API.
bot = Bot(token=BOT_TOKEN)

# [AIOGRAM] Dispatcher принимает входящие сообщения и распределяет их по handler-ам.
dp = Dispatcher()


# [AIOGRAM] CommandStart ловит команду /start.
@dp.message(CommandStart())
async def start(message: Message):
    # [AIOGRAM] WebAppInfo говорит Telegram, какой URL открыть как Mini App.
    web_app = WebAppInfo(url=WEB_APP_URL)

    # [AIOGRAM] InlineKeyboardButton создает кнопку под сообщением Telegram.
    open_catalog_button = InlineKeyboardButton(
        text='Открыть каталог',
        web_app=web_app,
    )

    # [AIOGRAM] InlineKeyboardMarkup показывает inline-кнопку под сообщением.
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[open_catalog_button]]
    )

    # [AIOGRAM] answer отправляет сообщение пользователю.
    await message.answer(
        'Откройте каталог и оформите заказ:',
        reply_markup=keyboard,
    )


# [OUR] main() запускает polling: бот постоянно спрашивает Telegram о новых сообщениях.
async def main():
    await dp.start_polling(bot)


# [PY] Этот блок запускается только если файл вызвали напрямую как python -m telegram_bot.main.
if __name__ == '__main__':
    asyncio.run(main())
