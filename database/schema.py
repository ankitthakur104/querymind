import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ecommerce.db")

def create_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Tables ---
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            city          TEXT,
            country       TEXT,
            joined_date   TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            product_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            category      TEXT,
            price         REAL,
            stock_qty     INTEGER
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id   INTEGER REFERENCES customers(customer_id),
            order_date    TEXT,
            status        TEXT,  -- 'pending', 'shipped', 'delivered', 'cancelled'
            total_amount  REAL
        );

        CREATE TABLE IF NOT EXISTS order_items (
            item_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id      INTEGER REFERENCES orders(order_id),
            product_id    INTEGER REFERENCES products(product_id),
            quantity      INTEGER,
            unit_price    REAL
        );
    """)

    # --- Seed data ---
    cursor.executemany(
        "INSERT OR IGNORE INTO customers (name, email, city, country, joined_date) VALUES (?,?,?,?,?)",
        [
            ("Alice Sharma",   "alice@example.com",  "Mumbai",    "India",  "2022-01-15"),
            ("Bob Chen",       "bob@example.com",    "Singapore", "Singapore", "2022-03-20"),
            ("Carol Davis",    "carol@example.com",  "London",    "UK",     "2021-11-05"),
            ("David Kim",      "david@example.com",  "Seoul",     "Korea",  "2023-02-10"),
            ("Eva Martinez",   "eva@example.com",    "Madrid",    "Spain",  "2022-07-30"),
        ]
    )

    cursor.executemany(
        "INSERT OR IGNORE INTO products (name, category, price, stock_qty) VALUES (?,?,?,?)",
        [
            ("Wireless Headphones", "Electronics",  89.99,  150),
            ("Python Cookbook",     "Books",        39.99,  300),
            ("Running Shoes",       "Sports",      119.99,   80),
            ("Coffee Maker",        "Appliances",   59.99,   60),
            ("Mechanical Keyboard", "Electronics", 149.99,  200),
            ("Data Science Guide",  "Books",        44.99,  250),
            ("Yoga Mat",            "Sports",       29.99,  400),
            ("Air Purifier",        "Appliances",  199.99,   40),
        ]
    )

    cursor.executemany(
        "INSERT OR IGNORE INTO orders (customer_id, order_date, status, total_amount) VALUES (?,?,?,?)",
        [
            (1, "2024-01-10", "delivered", 229.97),
            (1, "2024-03-05", "shipped",   149.99),
            (2, "2024-02-14", "delivered",  89.99),
            (3, "2024-01-20", "cancelled",  39.99),
            (3, "2024-03-18", "pending",   319.98),
            (4, "2024-02-28", "delivered",  59.99),
            (5, "2024-03-01", "shipped",   179.98),
        ]
    )

    cursor.executemany(
        "INSERT OR IGNORE INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?,?,?,?)",
        [
            (1, 1, 1,  89.99),
            (1, 3, 1, 119.99),
            (1, 7, 1,  29.99),  # headphones + shoes + yoga mat
            (2, 5, 1, 149.99),  # keyboard
            (3, 1, 1,  89.99),  # headphones
            (4, 2, 1,  39.99),  # book (cancelled)
            (5, 3, 1, 119.99),
            (5, 8, 1, 199.99),  # shoes + purifier
            (6, 4, 1,  59.99),  # coffee maker
            (7, 5, 1, 149.99),
            (7, 7, 1,  29.99),  # keyboard + yoga mat
        ]
    )

    conn.commit()
    conn.close()
    print(f"✅ Database created at: {DB_PATH}")

if __name__ == "__main__":
    create_database()