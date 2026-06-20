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

        quantities_by_product_id: dict[int, int] = {}
        for item in items:
            product_id = int(item["product_id"])
            quantity = int(item.get("quantity", 1))
            if quantity <= 0:
                raise ValueError("Quantity must be positive")
            quantities_by_product_id[product_id] = quantities_by_product_id.get(product_id, 0) + quantity

        product_ids = list(quantities_by_product_id)
        placeholders = ",".join("?" for _ in product_ids)
        products = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT
                  p.id,
                  p.name_short AS name,
                  p.price_cents,
                  c.sort_order AS category_sort_order,
                  mp.sort_order AS menu_sort_order,
                  p.sort_order AS product_sort_order
                FROM products p
                JOIN categories c ON c.id = p.category_id
                JOIN menu_products mp ON mp.product_id = p.id
                WHERE p.id IN ({placeholders})
                  AND p.enabled = 1
                  AND mp.menu_id = ?
                ORDER BY c.sort_order, mp.sort_order, p.sort_order, p.name_short
                """,
                (*product_ids, menu_id),
            )
        ]

        found_product_ids = {product["id"] for product in products}
        missing_product_ids = set(product_ids) - found_product_ids
        if missing_product_ids:
            raise ValueError(f"Product unavailable in menu {menu_slug}: {sorted(missing_product_ids)}")

        total_cents = 0
        normalized_items = []
        for product in products:
            product_id = int(product["id"])
            quantity = quantities_by_product_id[product_id]
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
