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
        # category, slug, full name, short name, acronym, price cents, enabled, sort order
        (cat_ids["coperti"], "coperto", "Coperto", "Coperto", "COP", 100, 1, 10),

        (cat_ids["bevande"], "vino_rosso", "Vino rosso bottiglia", "Vino rosso", "VR", 700, 1, 20),
        (cat_ids["bevande"], "vino_bianco", "Vino bianco bottiglia", "Vino bianco", "VB", 700, 1, 30),
        (cat_ids["bevande"], "birra", "Birra alla spina", "Birra", "BIR", 400, 1, 40),
        (cat_ids["bevande"], "fanta", "Fanta lattina", "Fanta", "FAN", 250, 1, 50),
        (cat_ids["bevande"], "coca", "Coca-Cola lattina", "Coca-Cola", "COC", 250, 1, 60),
        (cat_ids["bevande"], "acqua_gassata", "Acqua gassata bottiglia", "Acqua gas.", "AG", 150, 1, 70),
        (cat_ids["bevande"], "acqua_naturale", "Acqua naturale bottiglia", "Acqua nat.", "AN", 150, 1, 80),

        (cat_ids["antipasti"], "olive_assaggio", "Assaggio di olive", "Assaggio olive", "OLV", 150, 1, 90),
        (cat_ids["antipasti"], "bruschetta", "Bruschetta", "Bruschetta", "BRU", 200, 1, 100),
        (cat_ids["antipasti"], "piatto_freddo", "Piatto freddo", "Piatto freddo", "PF", 700, 1, 110),

        (cat_ids["panini"], "panino_prosciutto", "Panino con prosciutto", "Panino prosciutto", "PP", 300, 1, 120),
        (cat_ids["panini"], "panino_salame", "Panino con salame", "Panino salame", "PS", 300, 1, 130),

        (cat_ids["affettati"], "prosciutto", "Prosciutto 100 g", "Prosciutto", "PRO", 300, 1, 140),
        (cat_ids["affettati"], "salame", "Salame 100 g", "Salame", "SAL", 250, 1, 150),

        (cat_ids["primi"], "zuppa", "Zuppa", "Zuppa", "ZUP", 500, 1, 160),
        (cat_ids["primi"], "farro", "Farro", "Farro", "FAR", 500, 1, 170),
        (cat_ids["primi"], "penne_pomodoro", "Penne al pomodoro", "Penne pomodoro", "PPOM", 500, 1, 180),
        (cat_ids["primi"], "penne_ragu", "Penne al ragù", "Penne ragù", "PRAG", 600, 1, 190),

        (cat_ids["secondi_pesce"], "frittura", "Frittura di mare", "Frittura", "FRI", 1000, 1, 200),

        (cat_ids["secondi_carne"], "cinghiale", "Cinghiale in umido", "Cinghiale", "CIN", 950, 1, 210),
        (cat_ids["secondi_carne"], "grigliata", "Grigliata mista", "Grigliata", "GRI", 800, 1, 220),
        (cat_ids["secondi_carne"], "rosticciana", "Rosticciana", "Rosticciana", "ROS", 550, 1, 230),
        (cat_ids["secondi_carne"], "salsiccia", "Salsiccia", "Salsiccia", "SALC", 550, 1, 240),
        (cat_ids["secondi_carne"], "bistecca_maiale", "Bistecca di maiale", "Bistecca maiale", "BM", 550, 1, 250),
        (cat_ids["secondi_carne"], "bistecca_manzo", "Bistecca di manzo", "Bistecca manzo", "BMAN", 1400, 1, 260),
        (cat_ids["secondi_carne"], "galletto", "Mezzo galletto alla brace", "Mezzo galletto", "GAL", 600, 1, 270),

        (cat_ids["contorni"], "patatine", "Patatine fritte", "Patatine", "PAT", 250, 1, 280),
        (cat_ids["contorni"], "fagioli", "Fagioli", "Fagioli", "FAG", 250, 1, 290),
        (cat_ids["contorni"], "pomodori", "Pomodori", "Pomodori", "POM", 250, 1, 300),

        (cat_ids["dolci"], "fetta_di_torta", "Fetta di torta", "Fetta torta", "FT", 250, 1, 310),
        (cat_ids["dolci"], "torta_intera", "Torta intera", "Torta intera", "TI", 2000, 1, 320),

        (cat_ids["bar"], "caffe", "Caffè", "Caffè", "CAF", 100, 1, 330),
        (cat_ids["bar"], "corretto", "Caffè corretto", "Corretto", "COR", 150, 1, 340),
        (cat_ids["bar"], "amari", "Amari / grappe", "Amari/grappe", "AMA", 250, 1, 350),
        (cat_ids["bar"], "bicchiere_vino_rosso", "Bicchiere vino rosso", "Bicch. vino rosso", "BVR", 150, 1, 360),
        (cat_ids["bar"], "bicchiere_vino_bianco", "Bicchiere vino bianco", "Bicch. vino bianco", "BVB", 150, 1, 370),
        (cat_ids["bar"], "spumante_bicchiere", "Bicchiere spumante", "Bicch. spumante", "BS", 150, 1, 380),
        (cat_ids["bar"], "prosecco_bicchiere", "Bicchiere prosecco", "Bicch. prosecco", "BP", 150, 1, 390),
        (cat_ids["bar"], "spumante_bottiglia", "Bottiglia spumante", "Bott. spumante", "BSP", 150, 1, 400),
        (cat_ids["bar"], "prosecco_bottiglia", "Bottiglia prosecco", "Bott. prosecco", "BPR", 150, 1, 410),
        (cat_ids["bar"], "grappa_bottiglia", "Bottiglia grappa", "Bott. grappa", "BGR", 150, 1, 420),
        (cat_ids["bar"], "limoncello_bottiglia", "Bottiglia limoncello", "Bott. limoncello", "BLI", 150, 1, 430),
        (cat_ids["bar"], "spritz", "Spritz", "Spritz", "SPR", 500, 1, 440),

        (cat_ids["olive"], "olive_barattolo", "Barattolo olive", "Olive barattolo", "OB", 700, 1, 450),
    ]

    conn.executemany(
        """
        INSERT INTO products(category_id, slug, name, name_short, acronym, price_cents, enabled, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
