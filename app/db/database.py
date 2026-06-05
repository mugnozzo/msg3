from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "msg.sqlite3"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text())
        seed_if_empty(conn)


def seed_if_empty(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count:
        return

    categories = [("Coperti", 10), ("Bevande", 20), ("Cucina", 30), ("Bar", 40)]
    conn.executemany("INSERT INTO categories(name, sort_order) VALUES (?, ?)", categories)

    cat_ids = {row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM categories")}
    products = [
        (cat_ids["Coperti"], "Coperto", 200, 1, "🍽️", 10),
        (cat_ids["Bevande"], "Acqua", 100, 1, "💧", 20),
        (cat_ids["Bevande"], "Vino rosso", 500, 1, "🍷", 30),
        (cat_ids["Bevande"], "Vino bianco", 500, 1, "🥂", 40),
        (cat_ids["Bevande"], "Birra", 400, 1, "🍺", 50),
        (cat_ids["Bevande"], "Coca Cola", 300, 1, "🥤", 60),
        (cat_ids["Cucina"], "Bruschetta", 300, 1, "🥖", 70),
        (cat_ids["Cucina"], "Zuppa", 700, 1, "🍲", 80),
        (cat_ids["Cucina"], "Patatine", 350, 1, "🍟", 90),
        (cat_ids["Cucina"], "Grigliata", 1200, 1, "🔥", 100),
        (cat_ids["Bar"], "Caffè", 100, 1, "☕", 110),
    ]
    conn.executemany(
        """
        INSERT INTO products(category_id, name, price_cents, enabled, icon, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        products,
    )

    conn.executemany("INSERT INTO menus(slug, name) VALUES (?, ?)", [("main", "Cassa principale"), ("bar", "Bar")])
    menu_ids = {row["slug"]: row["id"] for row in conn.execute("SELECT id, slug FROM menus")}
    product_rows = list(conn.execute("SELECT id, name FROM products ORDER BY sort_order"))
    for idx, row in enumerate(product_rows):
        conn.execute(
            "INSERT INTO menu_products(menu_id, product_id, sort_order) VALUES (?, ?, ?)",
            (menu_ids["main"], row["id"], idx * 10),
        )
        if row["name"] in {"Acqua", "Vino rosso", "Vino bianco", "Birra", "Coca Cola", "Caffè"}:
            conn.execute(
                "INSERT INTO menu_products(menu_id, product_id, sort_order) VALUES (?, ?, ?)",
                (menu_ids["bar"], row["id"], idx * 10),
            )

    conn.execute("INSERT INTO cashiers(name) VALUES (?)", ("Cassa 1",))
    conn.execute("INSERT INTO printers(name, kind, address) VALUES (?, ?, ?)", ("Test file printer", "file", str(DATA_DIR / "printer-output.bin")))
    cashier_id = conn.execute("SELECT id FROM cashiers WHERE name = ?", ("Cassa 1",)).fetchone()[0]
    printer_id = conn.execute("SELECT id FROM printers WHERE name = ?", ("Test file printer",)).fetchone()[0]
    conn.execute(
        "INSERT INTO cashier_settings(cashier_id, printer_id, menu_id) VALUES (?, ?, ?)",
        (cashier_id, printer_id, menu_ids["main"]),
    )


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]
