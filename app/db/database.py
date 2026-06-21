from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "msg.sqlite3"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SEED_PATH = DATA_DIR / "seed.json"
SEED_SAMPLE_PATH = DATA_DIR / "seed.sample.json"
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

    seed = load_seed_data()
    seed_database(conn, seed)


def load_seed_data() -> dict[str, Any]:
    seed_path = SEED_PATH if SEED_PATH.exists() else SEED_SAMPLE_PATH
    if not seed_path.exists():
        raise FileNotFoundError(
            f"Seed file not found. Create {SEED_PATH} or keep {SEED_SAMPLE_PATH} available."
        )

    with seed_path.open("r", encoding="utf-8") as file:
        seed = json.load(file)

    if not isinstance(seed, dict):
        raise ValueError(f"Invalid seed file {seed_path}: root must be a JSON object")
    return seed


def seed_database(conn: sqlite3.Connection, seed: dict[str, Any]) -> None:
    categories = seed.get("categories", [])
    products = seed.get("products", [])
    menus = seed.get("menus", [])
    kitchen_screens = seed.get("kitchen_screens", [])
    cashiers = seed.get("cashiers", [])
    printers = seed.get("printers", [])
    cashier_settings = seed.get("cashier_settings", [])

    if not categories:
        raise ValueError("Seed must contain at least one category")
    if not products:
        raise ValueError("Seed must contain at least one product")
    if not menus:
        raise ValueError("Seed must contain at least one menu")

    conn.executemany(
        "INSERT INTO categories(name, sort_order) VALUES (?, ?)",
        [(item["name"], item.get("sort_order", 0)) for item in categories],
    )

    cat_ids = {
        row["name"]: row["id"]
        for row in conn.execute("SELECT id, name FROM categories")
    }

    product_rows = []
    for product in products:
        category_name = product["category"]
        if category_name not in cat_ids:
            raise ValueError(f"Unknown product category in seed: {category_name}")
        product_rows.append(
            (
                cat_ids[category_name],
                product["slug"],
                product["name"],
                product.get("name_short") or product["name"],
                product.get("acronym"),
                int(product["price_cents"]),
                int(product.get("enabled", 1)),
                product.get("image_path"),
                product.get("icon"),
                int(product.get("sort_order", 0)),
            )
        )

    conn.executemany(
        """
        INSERT INTO products(category_id, slug, name, name_short, acronym, price_cents, enabled, image_path, icon, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        product_rows,
    )

    conn.executemany(
        "INSERT INTO menus(slug, name) VALUES (?, ?)",
        [(item["slug"], item["name"]) for item in menus],
    )

    menu_ids = {
        row["slug"]: row["id"]
        for row in conn.execute("SELECT id, slug FROM menus")
    }
    product_ids = {
        row["slug"]: row["id"]
        for row in conn.execute("SELECT id, slug FROM products")
    }

    menu_product_rows = []
    for menu in menus:
        menu_slug = menu["slug"]
        for index, product_slug in enumerate(menu.get("products", []), start=1):
            if product_slug not in product_ids:
                raise ValueError(f"Unknown product in menu {menu_slug}: {product_slug}")
            product_sort_order = conn.execute(
                "SELECT sort_order FROM products WHERE slug = ?",
                (product_slug,),
            ).fetchone()[0]
            menu_product_rows.append(
                (menu_ids[menu_slug], product_ids[product_slug], product_sort_order or index * 10)
            )

    conn.executemany(
        """
        INSERT INTO menu_products(menu_id, product_id, sort_order)
        VALUES (?, ?, ?)
        """,
        menu_product_rows,
    )

    seed_kitchen_screens(conn, kitchen_screens, product_ids)

    for cashier in cashiers:
        conn.execute(
            "INSERT INTO cashiers(name, enabled) VALUES (?, ?)",
            (cashier["name"], int(cashier.get("enabled", 1))),
        )

    for printer in printers:
        address = printer.get("address")
        if address == "__DEFAULT_FILE_PRINTER_PATH__":
            address = str(DEFAULT_FILE_PRINTER_PATH)
        conn.execute(
            """
            INSERT INTO printers(name, kind, address, enabled, cut_enabled)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                printer["name"],
                printer.get("kind", "file"),
                address,
                int(printer.get("enabled", 1)),
                int(printer.get("cut_enabled", 1)),
            ),
        )

    cashier_ids = {
        row["name"]: row["id"]
        for row in conn.execute("SELECT id, name FROM cashiers")
    }
    printer_ids = {
        row["name"]: row["id"]
        for row in conn.execute("SELECT id, name FROM printers")
    }

    for setting in cashier_settings:
        cashier_name = setting["cashier"]
        printer_name = setting["printer"]
        menu_slug = setting["menu"]
        if cashier_name not in cashier_ids:
            raise ValueError(f"Unknown cashier in cashier_settings: {cashier_name}")
        if printer_name not in printer_ids:
            raise ValueError(f"Unknown printer in cashier_settings: {printer_name}")
        if menu_slug not in menu_ids:
            raise ValueError(f"Unknown menu in cashier_settings: {menu_slug}")
        conn.execute(
            """
            INSERT INTO cashier_settings(cashier_id, printer_id, menu_id, print_client_copy, print_waiter_copy)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cashier_ids[cashier_name],
                printer_ids[printer_name],
                menu_ids[menu_slug],
                int(setting.get("print_client_copy", 1)),
                int(setting.get("print_waiter_copy", 1)),
            ),
        )


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def seed_kitchen_screens(
    conn: sqlite3.Connection,
    kitchen_screens: list[dict[str, Any]],
    product_ids: dict[str, int],
) -> None:
    if not kitchen_screens:
        kitchen_screens = [
            {
                "name": "Grill",
                "slug": "grill",
                "sort_order": 10,
                "products": infer_default_grill_products(product_ids),
            }
        ]

    screen_rows = []
    for screen in kitchen_screens:
        screen_rows.append(
            (
                screen["name"],
                screen["slug"],
                int(screen.get("sort_order", 0)),
                int(screen.get("is_active", 1)),
            )
        )

    conn.executemany(
        """
        INSERT INTO kitchen_screens(name, slug, sort_order, is_active)
        VALUES (?, ?, ?, ?)
        """,
        screen_rows,
    )

    screen_ids = {
        row["slug"]: row["id"]
        for row in conn.execute("SELECT id, slug FROM kitchen_screens")
    }

    screen_product_rows = []
    for screen in kitchen_screens:
        screen_slug = screen["slug"]
        for index, product_slug in enumerate(screen.get("products", []), start=1):
            if product_slug not in product_ids:
                raise ValueError(f"Unknown product in kitchen screen {screen_slug}: {product_slug}")
            product_sort_order = conn.execute(
                "SELECT sort_order FROM products WHERE slug = ?",
                (product_slug,),
            ).fetchone()[0]
            screen_product_rows.append(
                (screen_ids[screen_slug], product_ids[product_slug], product_sort_order or index * 10)
            )

    conn.executemany(
        """
        INSERT INTO kitchen_screen_products(screen_id, product_id, sort_order)
        VALUES (?, ?, ?)
        """,
        screen_product_rows,
    )


def infer_default_grill_products(product_ids: dict[str, int]) -> list[str]:
    known_grill_slugs = [
        "penne_pomodoro",
        "penne_ragu",
        "frittura",
        "grigliata",
        "rosticciana",
        "salsiccia",
        "bistecca_maiale",
        "bistecca_manzo",
        "galletto",
    ]
    inferred = [slug for slug in known_grill_slugs if slug in product_ids]
    if inferred:
        return inferred
