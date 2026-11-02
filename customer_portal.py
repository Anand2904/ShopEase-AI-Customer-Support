
import sqlite3
import hashlib
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "customer_portal.db"


def hash_password(password, salt=None):
    """Hash a demo account password."""
    if salt is None:
        salt = os.urandom(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000,
    )

    return salt.hex(), password_hash.hex()


def initialize_database():
    """Create database tables and insert sample data once."""

    with sqlite3.connect(DB_FILE) as connection:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                amount REAL NOT NULL,
                order_date TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (customer_id)
                    REFERENCES customers(customer_id)
            )
        """)

        sample_customers = [
            ("Aarav Sharma", "aarav@example.com", "DemoPass123!"),
            ("Priya Kumar", "priya@example.com", "DemoPass123!"),
            ("Rahul Verma", "rahul@example.com", "DemoPass123!"),
        ]

        for name, email, password in sample_customers:
            salt, password_hash = hash_password(password)

            cursor.execute("""
                INSERT OR IGNORE INTO customers
                (name, email, password_salt, password_hash)
                VALUES (?, ?, ?, ?)
            """, (name, email, salt, password_hash))

        sample_orders = [
            ("SE1001", "aarav@example.com", "Wireless Headphones", 2499, "2026-10-25", "Shipped"),
            ("SE1002", "aarav@example.com", "Laptop Stand", 899, "2026-10-28", "Processing"),
            ("SE2001", "priya@example.com", "Smart Watch", 3999, "2026-10-20", "Delivered"),
            ("SE2002", "priya@example.com", "Bluetooth Speaker", 1599, "2026-10-29", "Shipped"),
            ("SE3001", "rahul@example.com", "Wireless Mouse", 799, "2026-10-30", "Processing"),
        ]

        for order in sample_orders:
            customer = cursor.execute(
                "SELECT customer_id FROM customers WHERE email = ?",
                (order[1],)
            ).fetchone()

            if customer:
                cursor.execute("""
                    INSERT OR IGNORE INTO orders
                    (order_id, customer_id, product_name, amount, order_date, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    order[0],
                    customer[0],
                    order[2],
                    order[3],
                    order[4],
                    order[5],
                ))


def authenticate_customer(email, password):
    """Check a demo customer's email and password."""

    with sqlite3.connect(DB_FILE) as connection:
        connection.row_factory = sqlite3.Row

        customer = connection.execute("""
            SELECT * FROM customers WHERE email = ?
        """, (email.strip().lower(),)).fetchone()

    if customer is None:
        return None

    salt, password_hash = hash_password(
        password,
        bytes.fromhex(customer["password_salt"]),
    )

    if password_hash != customer["password_hash"]:
        return None

    return {
        "customer_id": customer["customer_id"],
        "name": customer["name"],
        "email": customer["email"],
    }


def get_customer_orders(customer_id):
    """Return orders belonging only to the signed-in customer."""

    with sqlite3.connect(DB_FILE) as connection:
        connection.row_factory = sqlite3.Row

        orders = connection.execute("""
            SELECT order_id, product_name, amount, order_date, status
            FROM orders
            WHERE customer_id = ?
            ORDER BY order_date DESC
        """, (customer_id,)).fetchall()

    return [dict(order) for order in orders]


if __name__ == "__main__":
    initialize_database()
    print("Customer database initialized successfully!")
