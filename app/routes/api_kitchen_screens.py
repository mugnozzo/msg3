from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db.database import get_connection, rows_to_dicts

router = APIRouter(prefix="/api/kitchen-screens", tags=["kitchen-screens"])


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
