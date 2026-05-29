import asyncio
import logging
import sqlite3
from datetime import datetime
from os import getenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = getenv("BOT_TOKEN")
ADMIN_ID = int(getenv("ADMIN_ID")) if getenv("ADMIN_ID") else None

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot and Dispatcher initialization
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def init_db():
    try:
        with sqlite3.connect("shop.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price_stars INTEGER NOT NULL,
                    file_url TEXT NOT NULL,
                    description TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    date TEXT NOT NULL
                )
            """)
            conn.commit()
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    try:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Каталог", callback_data="catalog")]
        ])
        await message.answer("Добро пожаловать в магазин! Выберите раздел:", reply_markup=kb)
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}")

@dp.callback_query(F.data == "catalog")
async def show_catalog(callback: types.CallbackQuery):
    try:
        with sqlite3.connect("shop.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, price_stars FROM products")
            products = cursor.fetchall()

        if not products:
            await callback.answer("Каталог пока пуст.", show_alert=True)
            return

        buttons = []
        for product in products:
            buttons.append([InlineKeyboardButton(
                text=f"{product[1]} ({product[2]}⭐)", 
                callback_data=f"buy_{product[0]}"
            )])
        
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text("Выберите товар для покупки:", reply_markup=kb)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in show_catalog: {e}")
        await callback.answer("Произошла ошибка при загрузке каталога.", show_alert=True)

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    try:
        product_id = int(callback.data.split("_")[1])
        with sqlite3.connect("shop.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, price_stars, file_url, description FROM products WHERE id = ?", (product_id,))
            product = cursor.fetchone()

        if not product:
            await callback.answer("Товар не найден.", show_alert=True)
            return

        await callback.message.answer_invoice(
            title=product[1],
            description=product[4] if product[4] else "Цифровой товар",
            payload=f"product_{product[0]}",
            currency="XTR",
            prices=[LabeledPrice(label=product[1], amount=product[2])]
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in process_buy: {e}")
        await callback.answer("Ошибка при создании инвойса.", show_alert=True)

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    try:
        await pre_checkout_query.answer(ok=True)
    except Exception as e:
        logger.error(f"Error in pre_checkout_query: {e}")

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    try:
        payload = message.successful_payment.invoice_payload
        product_id = int(payload.split("_")[1])
        user_id = message.from_user.id

        with sqlite3.connect("shop.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_url FROM products WHERE id = ?", (product_id,))
            product_url = cursor.fetchone()[0]
            
            cursor.execute("INSERT INTO purchases (user_id, product_id, date) VALUES (?, ?, ?)", 
                           (user_id, product_id, datetime.now().isoformat()))
            conn.commit()

        await message.answer(f"Спасибо за покупку! Ваш файл: {product_url}")
    except Exception as e:
        logger.error(f"Error in successful_payment: {e}")
        await message.answer("Оплата прошла, но возникла ошибка при выдаче товара. Свяжитесь с администратором.")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if ADMIN_ID and message.from_user.id == ADMIN_ID:
        try:
            with sqlite3.connect("shop.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT p.name, COUNT(pur.id), SUM(p.price_stars) 
                    FROM products p 
                    LEFT JOIN purchases pur ON p.id = pur.product_id 
                    GROUP BY p.id
                """)
                stats = cursor.fetchall()

            if not stats:
                await message.answer("Данных о продажах нет.")
                return

            text = "📊 Статистика продаж:\n\n"
            for row in stats:
                name, count, total = row
                text += f"📦 {name}: {count or 0} шт. (Итого: {total or 0}⭐)\n"
            
            await message.answer(text)
        except Exception as e:
            logger.error(f"Error in cmd_stats: {e}")
            await message.answer("Ошибка при получении статистики.")
    else:
        await message.answer("У вас нет прав для этой команды.")

@dp.message(Command("addproduct"))
async def cmd_add_product(message: types.Message):
    if ADMIN_ID and message.from_user.id == ADMIN_ID:
        try:
            # Format: /addproduct Название|100|https://ссылка.zip|Описание
            args = message.text.split(maxsplit=1)[1]
            name, price, url, desc = args.split("|")
            
            with sqlite3.connect("shop.db") as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO products (name, price_stars, file_url, description) VALUES (?, ?, ?, ?)", 
                               (name.strip(), int(price.strip()), url.strip(), desc.strip()))
                conn.commit()
            
            await message.answer(f"Товар '{name}' успешно добавлен!")
        except (IndexError, ValueError) as e:
            logger.error(f"Invalid format in addproduct: {e}")
            await message.answer("Ошибка формата. Используйте:\n/addproduct Название|100|https://ссылка.zip|Описание")
        except Exception as e:
            logger.error(f"Error in cmd_add_product: {e}")
            await message.answer("Произошла внутренняя ошибка.")
    else:
        await message.answer("У вас нет прав для этой команды.")

async def main():
    init_db()
    logger.info("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")