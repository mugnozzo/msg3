from __future__ import annotations

from app.db.database import get_connection
from app.services.print_service import create_and_process_print_job


def create_order(items: list[dict], cashier_id: int = 1, menu_slug: str = "main", print_now: bool = True) -> dict:
    if not items:
        raise ValueError("Order must contain at least one item")

    with get_connection() as conn:
        menu = conn.execute("SELECT id FROM menus WHERE slug = ?", (menu_slug,)).fetchone()
        if menu is None:
            raise ValueError(f"Unknown menu: {menu_slug}")
        menu_id = menu["id"]

        product_ids = [int(item["product_id"]) for item in items]
        placeholders = ",".join("?" for _ in product_ids)
        products = {
            row["id"]: dict(row)
            for row in conn.execute(f"SELECT * FROM products WHERE id IN ({placeholders}) AND enabled = 1", product_ids)
        }

        total_cents = 0
        normalized_items = []
        for item in items:
            product_id = int(item["product_id"])
            quantity = int(item.get("quantity", 1))
            if quantity <= 0:
                raise ValueError("Quantity must be positive")
            product = products.get(product_id)
            if product is None:
                raise ValueError(f"Product unavailable: {product_id}")
            line_total = product["price_cents"] * quantity
            total_cents += line_total
            normalized_items.append((product_id, product["name"], product["price_cents"], quantity, line_total))

        next_number = conn.execute("SELECT COALESCE(MAX(order_number), 0) + 1 FROM orders").fetchone()[0]
        cur = conn.execute(
            "INSERT INTO orders(order_number, cashier_id, menu_id, total_cents) VALUES (?, ?, ?, ?)",
            (next_number, cashier_id, menu_id, total_cents),
        )
        order_id = cur.lastrowid
        conn.executemany(
            """
            INSERT INTO order_items(order_id, product_id, name_snapshot, price_cents_snapshot, quantity, line_total_cents)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [(order_id, *row) for row in normalized_items],
        )
        setting = conn.execute("SELECT printer_id FROM cashier_settings WHERE cashier_id = ?", (cashier_id,)).fetchone()
        printer_id = setting["printer_id"] if setting else 1

    print_job_id = None
    if print_now:
        print_job_id = create_and_process_print_job(int(order_id), int(printer_id))

    return {"id": order_id, "order_number": next_number, "total_cents": total_cents, "print_job_id": print_job_id}
