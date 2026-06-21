from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.database import get_connection, rows_to_dicts

router = APIRouter(prefix="/api/kitchen-screens", tags=["kitchen-screens"])

_SLUG_RE = re.compile(r"^[a-z0-9_]+$")


class KitchenScreenIn(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    sort_order: int = 0
    is_active: bool = True
    product_ids: list[int] = []


def _clean_screen_payload(payload: KitchenScreenIn) -> dict:
    slug = payload.slug.strip().lower().replace("-", "_")
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=400, detail="Slug non valido: usa solo lettere minuscole, numeri e underscore")
    return {
        "name": payload.name.strip(),
        "slug": slug,
        "sort_order": payload.sort_order,
        "is_active": int(payload.is_active),
    }


@router.get("")
def list_kitchen_screens() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, slug, sort_order, is_active
            FROM kitchen_screens
            WHERE is_active = 1
            ORDER BY sort_order, name
            """
        )
        return rows_to_dicts(rows)


@router.get("/admin")
def list_kitchen_screens_admin() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, slug, sort_order, is_active
            FROM kitchen_screens
            ORDER BY sort_order, name
            """
        )
        screens = []
        for row in rows:
            screen = dict(row)
            screen["product_ids"] = [
                product_row["product_id"]
                for product_row in conn.execute(
                    """
                    SELECT product_id
                    FROM kitchen_screen_products
                    WHERE screen_id = ?
                    ORDER BY sort_order, product_id
                    """,
                    (screen["id"],),
                )
            ]
            screen["product_names"] = [
                product_row["name_short"] or product_row["name"]
                for product_row in conn.execute(
                    """
                    SELECT p.name, p.name_short
                    FROM kitchen_screen_products ksp
                    JOIN products p ON p.id = ksp.product_id
                    WHERE ksp.screen_id = ?
                    ORDER BY ksp.sort_order, p.sort_order, p.name
                    """,
                    (screen["id"],),
                )
            ]
            screens.append(screen)
        return screens


@router.get("/{slug}/totals")
def get_kitchen_screen_totals(slug: str) -> dict:
    with get_connection() as conn:
        screen = conn.execute(
            """
            SELECT id, name, slug, sort_order, is_active
            FROM kitchen_screens
            WHERE slug = ? AND is_active = 1
            """,
            (slug,),
        ).fetchone()
        if screen is None:
            raise HTTPException(status_code=404, detail="Kitchen screen not found")

        rows = conn.execute(
            """
            SELECT
              p.id,
              p.slug,
              p.name,
              p.name_short,
              p.acronym,
              COALESCE(p.image_path, '/static/img/products/' || p.slug || '.png') AS image_path,
              ksp.sort_order AS kitchen_sort_order,
              COALESCE(SUM(CASE WHEN o.id IS NOT NULL THEN oi.quantity ELSE 0 END), 0) AS quantity_total
            FROM kitchen_screen_products ksp
            JOIN products p ON p.id = ksp.product_id
            LEFT JOIN order_items oi ON oi.product_id = p.id
            LEFT JOIN orders o ON o.id = oi.order_id AND o.status = 'created'
            WHERE ksp.screen_id = ? AND p.enabled = 1
            GROUP BY p.id
            ORDER BY ksp.sort_order, p.sort_order, p.name
            """,
            (screen["id"],),
        )
        products = rows_to_dicts(rows)
        return {
            "screen": dict(screen),
            "products": products,
            "total_items": sum(int(product["quantity_total"]) for product in products),
        }


@router.post("")
def create_kitchen_screen(payload: KitchenScreenIn) -> dict:
    clean = _clean_screen_payload(payload)
    with get_connection() as conn:
        duplicate = conn.execute("SELECT id FROM kitchen_screens WHERE slug = ?", (clean["slug"],)).fetchone()
        if duplicate is not None:
            raise HTTPException(status_code=400, detail="Slug già usato")
        cur = conn.execute(
            """
            INSERT INTO kitchen_screens(name, slug, sort_order, is_active)
            VALUES (?, ?, ?, ?)
            """,
            (clean["name"], clean["slug"], clean["sort_order"], clean["is_active"]),
        )
        screen_id = int(cur.lastrowid)
        _replace_screen_products(conn, screen_id, payload.product_ids)
        return {"id": screen_id}


@router.put("/{screen_id:int}")
def update_kitchen_screen(screen_id: int, payload: KitchenScreenIn) -> dict:
    clean = _clean_screen_payload(payload)
    with get_connection() as conn:
        exists = conn.execute("SELECT id FROM kitchen_screens WHERE id = ?", (screen_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Kitchen screen not found")
        duplicate = conn.execute(
            "SELECT id FROM kitchen_screens WHERE slug = ? AND id <> ?",
            (clean["slug"], screen_id),
        ).fetchone()
        if duplicate is not None:
            raise HTTPException(status_code=400, detail="Slug già usato")
        conn.execute(
            """
            UPDATE kitchen_screens
            SET name = ?, slug = ?, sort_order = ?, is_active = ?
            WHERE id = ?
            """,
            (clean["name"], clean["slug"], clean["sort_order"], clean["is_active"], screen_id),
        )
        _replace_screen_products(conn, screen_id, payload.product_ids)
        return {"ok": True}


@router.delete("/{screen_id:int}")
def delete_kitchen_screen(screen_id: int) -> dict:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM kitchen_screens WHERE id = ?", (screen_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Kitchen screen not found")
        return {"ok": True}


def _replace_screen_products(conn, screen_id: int, product_ids: list[int]) -> None:
    conn.execute("DELETE FROM kitchen_screen_products WHERE screen_id = ?", (screen_id,))
    clean_ids = []
    seen = set()
    for product_id in product_ids:
        clean_id = int(product_id)
        if clean_id not in seen:
            clean_ids.append(clean_id)
            seen.add(clean_id)

    for index, product_id in enumerate(clean_ids, start=1):
        product = conn.execute(
            "SELECT id, sort_order FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if product is None:
            raise HTTPException(status_code=400, detail=f"Unknown product id: {product_id}")
        sort_order = product["sort_order"] or index * 10
        conn.execute(
            """
            INSERT INTO kitchen_screen_products(screen_id, product_id, sort_order)
            VALUES (?, ?, ?)
            """,
            (screen_id, product_id, sort_order),
        )
