from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "msg.sqlite3"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_FILE_PRINTER_PATH = DATA_DIR / "printer-output.bin"


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

    categories = [
        ("coperti", 10),
        ("bevande", 20),
        ("antipasti", 30),
        ("panini", 40),
        ("affettati", 50),
        ("primi", 60),
        ("secondi_pesce", 70),
        ("secondi_carne", 80),
        ("contorni", 90),
        ("dolci", 100),
        ("bar", 110),
        ("olive", 120),
    ]

    conn.executemany(
        "INSERT INTO categories(name, sort_order) VALUES (?, ?)",
        categories,
    )

    cat_ids = {
        row["name"]: row["id"]
        for row in conn.execute("SELECT id, name FROM categories")
    }

    products = [
        (cat_ids["coperti"], "coperto", 100, 1, "🍽️", 10),

        (cat_ids["bevande"], "vino rosso bott", 700, 1, "🍷", 20),
        (cat_ids["bevande"], "vino bianco bott", 700, 1, "🥂", 30),
        (cat_ids["bevande"], "birra alla spina", 400, 1, "🍺", 40),
        (cat_ids["bevande"], "fanta", 250, 1, "🥤", 50),
        (cat_ids["bevande"], "coca cola", 250, 1, "🥤", 60),
        (cat_ids["bevande"], "acqua gassata", 150, 1, "💧", 70),
        (cat_ids["bevande"], "acqua naturale", 150, 1, "💧", 80),

        (cat_ids["antipasti"], "assaggio olive", 150, 1, "🫒", 90),
        (cat_ids["antipasti"], "bruschetta", 200, 1, "🥖", 100),
        (cat_ids["antipasti"], "piatto freddo", 700, 1, "🥗", 110),

        (cat_ids["panini"], "panino prosciutto", 300, 1, "🥪", 120),
        (cat_ids["panini"], "panino salame", 300, 1, "🥪", 130),

        (cat_ids["affettati"], "prosciutto (etto)", 300, 1, "🍖", 140),
        (cat_ids["affettati"], "salame (etto)", 250, 1, "🍖", 150),

        (cat_ids["primi"], "zuppa", 500, 1, "🍲", 160),
        (cat_ids["primi"], "farro", 500, 1, "🌾", 170),
        (cat_ids["primi"], "penne al pomodoro", 500, 1, "🍝", 180),
        (cat_ids["primi"], "penne al ragù", 600, 1, "🍝", 190),

        (cat_ids["secondi_pesce"], "frittura di mare", 1000, 1, "🐟", 200),

        (cat_ids["secondi_carne"], "cinghiale in umido", 950, 1, "🍖", 210),
        (cat_ids["secondi_carne"], "grigliata mista", 800, 1, "🔥", 220),
        (cat_ids["secondi_carne"], "rosticciana", 550, 1, "🔥", 230),
        (cat_ids["secondi_carne"], "salsiccia", 550, 1, "🌭", 240),
        (cat_ids["secondi_carne"], "bistecca di maiale", 550, 1, "🥩", 250),
        (cat_ids["secondi_carne"], "bistecca di manzo", 1400, 1, "🥩", 260),
        (cat_ids["secondi_carne"], "galletto", 600, 1, "🍗", 270),

        (cat_ids["contorni"], "patatine", 250, 1, "🍟", 280),
        (cat_ids["contorni"], "fagioli", 250, 1, "🫘", 290),
        (cat_ids["contorni"], "pomodori", 250, 1, "🍅", 300),

        (cat_ids["dolci"], "fetta di torta", 250, 1, "🍰", 310),
        (cat_ids["dolci"], "torta intera", 2000, 1, "🎂", 320),

        (cat_ids["bar"], "caffè", 100, 1, "☕", 330),
        (cat_ids["bar"], "corretto", 150, 1, "☕", 340),
        (cat_ids["bar"], "amari/grappe", 250, 1, "🥃", 350),
        (cat_ids["bar"], "bicchiere vino", 150, 1, "🍷", 360),
        (cat_ids["bar"], "bicchiere spumante", 150, 1, "🥂", 370),
        (cat_ids["bar"], "spritz", 500, 1, "🍹", 380),

        (cat_ids["olive"], "olive barattolo", 700, 1, "🫒", 390),
    ]

    conn.executemany(
        """
        INSERT INTO products(category_id, name, price_cents, enabled, icon, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        products,
    )

    conn.executemany(
        "INSERT INTO menus(slug, name) VALUES (?, ?)",
        [
            ("main", "Cassa principale"),
            ("bar", "Bar"),
        ],
    )

    menu_ids = {
        row["slug"]: row["id"]
        for row in conn.execute("SELECT id, slug FROM menus")
    }

    product_rows = list(
        conn.execute(
            """
            SELECT p.id, p.name, c.name AS category_name, p.sort_order
            FROM products p
            JOIN categories c ON c.id = p.category_id
            ORDER BY p.sort_order
            """
        )
    )

    for row in product_rows:
        # Main cash desk: everything except bar-only products
        conn.execute(
            """
            INSERT INTO menu_products(menu_id, product_id, sort_order)
            VALUES (?, ?, ?)
            """,
            (menu_ids["main"], row["id"], row["sort_order"]),
        )

        # Bar cash desk: beverages + bar products
        if row["category_name"] in {"bevande", "bar", "dolci"}:
            conn.execute(
                """
                INSERT INTO menu_products(menu_id, product_id, sort_order)
                VALUES (?, ?, ?)
                """,
                (menu_ids["bar"], row["id"], row["sort_order"]),
            )

    conn.execute("INSERT INTO cashiers(name, enabled) VALUES (?, ?)", ("Cassa 1", 1))
    conn.execute("INSERT INTO printers(name, kind, address) VALUES (?, ?, ?)", ("Test file printer", "file", str(DEFAULT_FILE_PRINTER_PATH)))
    cashier_id = conn.execute("SELECT id FROM cashiers WHERE name = ?", ("Cassa 1",)).fetchone()[0]
    printer_id = conn.execute("SELECT id FROM printers WHERE name = ?", ("Test file printer",)).fetchone()[0]
    conn.execute(
        "INSERT INTO cashier_settings(cashier_id, printer_id, menu_id) VALUES (?, ?, ?)",
        (cashier_id, printer_id, menu_ids["main"]),
    )


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]
