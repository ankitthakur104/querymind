import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import sqlite3
import random
from faker import Faker
from database.schema import DB_PATH, create_database

fake = Faker()
Faker.seed(42)
random.seed(42)

# ── Config ─────────────────────────────────────────────────────────
NUM_CUSTOMERS = 200
NUM_PRODUCTS  = 50
NUM_ORDERS    = 500

# ── Product catalog ────────────────────────────────────────────────
PRODUCTS = [
    # Electronics
    ("Wireless Headphones",      "Electronics",  89.99,  150),
    ("Mechanical Keyboard",      "Electronics", 149.99,  200),
    ("USB-C Hub",                "Electronics",  49.99,  300),
    ("Webcam HD 1080p",          "Electronics",  79.99,  180),
    ("Portable SSD 1TB",         "Electronics", 109.99,  120),
    ("Smart Watch",              "Electronics", 199.99,   90),
    ("Noise Cancelling Earbuds", "Electronics", 129.99,  160),
    ("Monitor 27 inch",          "Electronics", 349.99,   45),
    ("Laptop Stand",             "Electronics",  39.99,  250),
    ("Gaming Mouse",             "Electronics",  59.99,  200),

    # Books
    ("Python Cookbook",          "Books",  39.99, 300),
    ("Data Science Guide",       "Books",  44.99, 250),
    ("Clean Code",               "Books",  34.99, 400),
    ("Designing Data Systems",   "Books",  54.99, 180),
    ("ML Engineering",           "Books",  49.99, 220),
    ("Deep Learning Basics",     "Books",  44.99, 190),
    ("System Design Interview",  "Books",  39.99, 350),
    ("The Pragmatic Programmer", "Books",  42.99, 280),
    ("LLM Engineering",          "Books",  52.99, 150),
    ("AI for Everyone",          "Books",  29.99, 500),

    # Sports
    ("Running Shoes",            "Sports", 119.99,  80),
    ("Yoga Mat",                 "Sports",  29.99, 400),
    ("Resistance Bands Set",     "Sports",  19.99, 600),
    ("Dumbbell Set 20kg",        "Sports",  89.99,  60),
    ("Cycling Helmet",           "Sports",  69.99, 100),
    ("Jump Rope",                "Sports",  12.99, 800),
    ("Foam Roller",              "Sports",  24.99, 350),
    ("Pull Up Bar",              "Sports",  34.99, 200),
    ("Protein Shaker",           "Sports",   9.99, 900),
    ("Sports Water Bottle",      "Sports",  19.99, 700),

    # Appliances
    ("Coffee Maker",             "Appliances",  59.99,  60),
    ("Air Purifier",             "Appliances", 199.99,  40),
    ("Electric Kettle",          "Appliances",  34.99, 150),
    ("Blender Pro",              "Appliances",  79.99,  80),
    ("Rice Cooker",              "Appliances",  49.99, 100),
    ("Toaster Oven",             "Appliances",  69.99,  70),
    ("Hand Mixer",               "Appliances",  29.99, 200),
    ("Vacuum Cleaner",           "Appliances", 149.99,  55),
    ("Air Fryer",                "Appliances",  89.99,  90),
    ("Dish Drying Rack",         "Appliances",  24.99, 300),

    # Books (more)
    ("FastAPI in Practice",      "Books",  44.99, 200),
    ("Docker Deep Dive",         "Books",  39.99, 180),
    ("Kubernetes Basics",        "Books",  49.99, 160),

    # Electronics (more)
    ("Bluetooth Speaker",        "Electronics",  69.99, 200),
    ("Phone Stand",              "Electronics",  14.99, 500),
    ("Cable Management Kit",     "Electronics",  19.99, 400),

    # Sports (more)
    ("Gym Bag",                  "Sports",  39.99, 250),
    ("Knee Sleeves",             "Sports",  24.99, 300),
    ("Exercise Mat",             "Sports",  34.99, 200),
    ("Adjustable Bench",         "Sports", 129.99,  40),
    ("Skipping Rope",            "Sports",   8.99, 600),
]

ORDER_STATUSES = ["pending", "shipped", "delivered", "delivered", "delivered", "cancelled"]
# delivered weighted higher — more realistic

COUNTRIES = [
    ("India", ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Pune"]),
    ("USA",   ["New York", "San Francisco", "Austin", "Seattle", "Chicago"]),
    ("UK",    ["London", "Manchester", "Birmingham", "Edinburgh"]),
    ("Germany", ["Berlin", "Munich", "Hamburg", "Frankfurt"]),
    ("Singapore", ["Singapore"]),
    ("Australia", ["Sydney", "Melbourne", "Brisbane"]),
    ("Canada", ["Toronto", "Vancouver", "Montreal"]),
    ("Japan", ["Tokyo", "Osaka", "Kyoto"]),
]


def seed(reset: bool = True):
    """
    Seeds the database with realistic fake data.
    reset=True → wipes existing data and starts fresh.
    reset=False → appends to existing data.
    """
    if reset:
        print("🗑️  Resetting database...")
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        create_database()  # recreate fresh schema

    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── 1. Insert products ─────────────────────────────────────────
    print(f"📦 Inserting {len(PRODUCTS)} products...")
    cursor.executemany(
        "INSERT OR IGNORE INTO products (name, category, price, stock_qty) VALUES (?,?,?,?)",
        PRODUCTS
    )
    conn.commit()

    # Get product IDs for order generation
    cursor.execute("SELECT product_id, price FROM products")
    product_rows = cursor.fetchall()
    product_ids  = [r[0] for r in product_rows]
    price_map    = {r[0]: r[1] for r in product_rows}

    # ── 2. Insert customers ────────────────────────────────────────
    print(f"👥 Inserting {NUM_CUSTOMERS} customers...")
    customers = []
    emails_used = set()

    for _ in range(NUM_CUSTOMERS):
        country, cities = random.choice(COUNTRIES)
        city  = random.choice(cities)
        email = fake.email()
        # ensure unique emails
        while email in emails_used:
            email = fake.email()
        emails_used.add(email)

        customers.append((
            fake.name(),
            email,
            city,
            country,
            fake.date_between(start_date="-3y", end_date="-1m").isoformat(),
        ))

    cursor.executemany(
        "INSERT OR IGNORE INTO customers (name, email, city, country, joined_date) VALUES (?,?,?,?,?)",
        customers
    )
    conn.commit()

    # Get customer IDs
    cursor.execute("SELECT customer_id FROM customers")
    customer_ids = [r[0] for r in cursor.fetchall()]

    # ── 3. Insert orders + order_items ────────────────────────────
    print(f"🛒 Inserting {NUM_ORDERS} orders with items...")
    orders_inserted = 0

    for _ in range(NUM_ORDERS):
        customer_id  = random.choice(customer_ids)
        status       = random.choice(ORDER_STATUSES)
        order_date   = fake.date_between(start_date="-1y", end_date="today").isoformat()

        # Each order has 1-4 items
        num_items    = random.randint(1, 4)
        items        = []
        total_amount = 0.0

        chosen_products = random.sample(product_ids, min(num_items, len(product_ids)))
        for pid in chosen_products:
            qty        = random.randint(1, 3)
            unit_price = price_map[pid]
            total_amount += qty * unit_price
            items.append((pid, qty, unit_price))

        total_amount = round(total_amount, 2)

        # Insert order
        cursor.execute(
            "INSERT INTO orders (customer_id, order_date, status, total_amount) VALUES (?,?,?,?)",
            (customer_id, order_date, status, total_amount)
        )
        order_id = cursor.lastrowid

        # Insert order items
        cursor.executemany(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?,?,?,?)",
            [(order_id, pid, qty, price) for pid, qty, price in items]
        )
        orders_inserted += 1

    conn.commit()
    conn.close()

    # ── 4. Print summary ───────────────────────────────────────────
    print("\n✅ Seeding complete!")
    print(f"   Customers : {NUM_CUSTOMERS}")
    print(f"   Products  : {len(PRODUCTS)}")
    print(f"   Orders    : {NUM_ORDERS}")
    print(f"\n   Database  : {DB_PATH}")


if __name__ == "__main__":
    seed(reset=True)