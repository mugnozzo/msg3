#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import DB_PATH, SCHEMA_PATH, get_connection  # noqa: E402

DEFAULT_STOCK_ITEMS = [
    ("girelli_salsiccia", "Girelli salsiccia", "girelli", 10),
    ("bistecche_maiale", "Bistecche maiale", "bistecche", 20),
    ("porzioni_rosticciana", "Porzioni rosticciana", "porzioni", 30),
]

# quantity_milli: 1000 = 1 unit, 500 = 0.5, 750 = 0.75.
DEFAULT_USAGE_RULES = [
    ("girelli_salsiccia", 2000, ["salsiccia_alla_brace", "salsiccia", "salsicce"], ["salsiccia"]),
    ("girelli_salsiccia", 1000, ["grigliata_mista", "grigliata"], ["grigliata"]),
    ("bistecche_maiale", 1000, ["bistecca_maiale", "bistecca_di_maiale"], ["bistecca", "maiale"]),
    ("bistecche_maiale", 500, ["grigliata_mista", "grigliata"], ["grigliata"]),
    ("porzioni_rosticciana", 1000, ["rosticciana"], ["rosticciana"]),
    ("porzioni_rosticciana", 750, ["grigliata_mista", "grigliata"], ["grigliata"]),
]


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text())


def upsert_stock_items(conn: sqlite3.Connection) -> None:
    for slug, name, unit_name, sort_order in DEFAULT_STOCK_ITEMS:
        conn.execute(
            """
            INSERT INTO stock_items(slug, name, unit_name, enabled, sort_order)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(slug) DO UPDATE SET
              name = excluded.name,
              unit_name = excluded.unit_name,
              sort_order = excluded.sort_order
            """,
            (slug, name, unit_name, sort_order),
        )


def find_product_id(conn: sqlite3.Connection, candidate_slugs: list[str], required_name_terms: list[str]) -> int | None:
    for slug in candidate_slugs:
        row = conn.execute("SELECT id FROM products WHERE slug = ?", (slug,)).fetchone()
        if row:
            return int(row["id"])

    where = " AND ".join("LOWER(name || ' ' || name_short || ' ' || slug) LIKE ?" for _ in required_name_terms)
    params = [f"%{term.lower()}%" for term in required_name_terms]
    row = conn.execute(
        f"SELECT id FROM products WHERE {where} ORDER BY sort_order, id LIMIT 1",
        params,
    ).fetchone()
    return int(row["id"]) if row else None


def upsert_usage_rules(conn: sqlite3.Connection) -> list[str]:
    messages = []
    stock_ids = {row["slug"]: row["id"] for row in conn.execute("SELECT id, slug FROM stock_items")}
    for stock_slug, quantity_milli, candidate_slugs, name_terms in DEFAULT_USAGE_RULES:
        product_id = find_product_id(conn, candidate_slugs, name_terms)
        if product_id is None:
            messages.append(f"SKIP: product not found for {stock_slug} / {candidate_slugs}")
            continue
        stock_id = stock_ids[stock_slug]
        conn.execute(
            """
            INSERT INTO product_stock_usages(product_id, stock_item_id, quantity_milli)
            VALUES (?, ?, ?)
            ON CONFLICT(product_id, stock_item_id) DO UPDATE SET
              quantity_milli = excluded.quantity_milli
            """,
            (product_id, stock_id, quantity_milli),
        )
        product = conn.execute("SELECT slug, name_short FROM products WHERE id = ?", (product_id,)).fetchone()
        messages.append(f"OK: {product['slug']} consumes {quantity_milli}/1000 of {stock_slug}")
    return messages


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")
    with get_connection() as conn:
        ensure_schema(conn)
        upsert_stock_items(conn)
        messages = upsert_usage_rules(conn)
    print("Migration 001 completed.")
    for message in messages:
        print(message)
    print("Set nightly quantities from /settings/stock before opening cash desks.")


if __name__ == "__main__":
    main()
