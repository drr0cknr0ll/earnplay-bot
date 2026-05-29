import sqlite3

def init_db_and_seed():
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    
    # Создаём таблицы (как в bot.py)
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
    
    # Добавляем 3 тестовых товара (если их ещё нет)
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        products = [
            (1, 'Парсер Wildberries', 100, 'https://example.com/wb_parser.zip', 'Готовый парсер карточек товаров WB'),
            (2, 'Шаблон реферального бота', 150, 'https://example.com/refbot.zip', 'Реферальная система под ключ'),
            (3, '50 промптов для ChatGPT', 50, 'https://example.com/prompts.zip', 'Рабочие промпты для маркетинга')
        ]
        cursor.executemany("INSERT INTO products (id, name, price_stars, file_url, description) VALUES (?, ?, ?, ?, ?)", products)
        print("✅ Добавлены 3 товара.")
    else:
        print("⚠️ Товары уже есть, база не тронута.")
    
    conn.commit()
    conn.close()
    print("База данных готова.")

if __name__ == "__main__":
    init_db_and_seed()