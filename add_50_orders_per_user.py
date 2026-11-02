"""Add 50 fictional sample orders for EACH existing customer (idempotent).

Run from the ShopEase project folder: python add_50_orders_per_user.py
Uses the existing customer_portal.db; does not remove or edit existing orders.
"""
from datetime import date, timedelta
from pathlib import Path
import random
import sqlite3

DB_PATH = Path(__file__).resolve().parent / "customer_portal.db"
ORDERS_PER_CUSTOMER = 50
PRODUCTS = [
    ("Wireless Headphones", 2499), ("Smart Watch", 3999),
    ("Bluetooth Speaker", 1799), ("Laptop Backpack", 1299),
    ("USB-C Charger", 899), ("Running Shoes", 2199),
    ("Mechanical Keyboard", 3299), ("Wireless Mouse", 999),
    ("Phone Case", 499), ("Power Bank", 1599),
    ("Laptop Stand", 1499), ("Water Bottle", 699),
    ("Desk Lamp", 1199), ("Yoga Mat", 899),
    ("Fitness Band", 2799), ("Portable SSD", 5499),
    ("Travel Mug", 799), ("Webcam", 2499),
    ("Notebook Set", 349), ("Mini Tripod", 1099),
]
STATUSES = ["Delivered"] * 6 + ["Shipped"] * 3 + ["Processing"]


def main():
    if not DB_PATH.is_file():
        raise SystemExit(f"Database not found: {DB_PATH}\nPlace this script beside customer_portal.db.")

    connection = sqlite3.connect(DB_PATH)
    try:
        customer_rows = connection.execute(
            "SELECT customer_id FROM customers ORDER BY customer_id"
        ).fetchall()
        if not customer_rows:
            raise SystemExit("No customers found. Start the customer portal once to initialize demo accounts.")

        total_added = 0
        for (customer_id,) in customer_rows:
            rng = random.Random(20261102 + int(customer_id))
            rows = []
            for i in range(1, ORDERS_PER_CUSTOMER + 1):
                product, base_price = PRODUCTS[(i - 1) % len(PRODUCTS)]
                amount = round(base_price * rng.choice([0.85, 0.9, 1.0, 1.0, 1.1]), 2)
                order_day = date(2026, 10, 31) - timedelta(days=rng.randint(1, 180))
                status = rng.choice(STATUSES)
                # Distinct namespace prevents collisions with existing SE1001/SE2001 orders.
                order_id = f"DEMO{int(customer_id):04d}{i:03d}"
                rows.append((order_id, customer_id, product, amount, order_day.isoformat(), status))

            before = connection.total_changes
            connection.executemany(
                """INSERT OR IGNORE INTO orders
                   (order_id, customer_id, product_name, amount, order_date, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                rows,
            )
            added = connection.total_changes - before
            total_added += added
            print(f"Customer ID {customer_id}: {added} new orders added (up to {ORDERS_PER_CUSTOMER} demo orders).")

        connection.commit()
        print(f"\nDone: {total_added} new orders added across {len(customer_rows)} customer(s).")
        print("Existing orders are unchanged. Running again will skip the same demo order IDs.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
