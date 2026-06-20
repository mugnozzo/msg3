from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.database import get_connection, rows_to_dicts

router = APIRouter(prefix="/api/products", tags=["products"])

_SLUG_RE = re.compile(r"^[a-z0-9_]+$")


class ProductIn(BaseModel):
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    name_short: str = Field(min_length=1)
    acronym: str | None = None
    price_cents: int = Field(ge=0)
    category_id: int
    enabled: bool = True
    icon: str | None = None
    image_path: str | None = None
    sort_order: int = 0
    menu_ids: list[int] = []


def _clean_product_payload(payload: ProductIn) -> dict:
    slug = payload.slug.strip().lower().replace("-", "_")
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=400, detail="Slug non valido: usa solo lettere minuscole, numeri e underscore")
    return {
        "slug": slug,
        "name": payload.name.strip(),
        "name_short": payload.name_short.strip(),
        "acronym": (payload.acronym or "").strip().upper() or None,
        "price_cents": payload.price_cents,
        "category_id": payload.category_id,
        "enabled": int(payload.enabled),
        "icon": payload.icon,
        "image_path": payload.image_path,
        "sort_order": payload.sort_order,
    }


@router.get("")
def list_products(menu: str = "main", include_disabled: bool = False) -> list[dict]:
    with get_connection() as conn:
        disabled_filter = "" if include_disabled else "AND p.enabled = 1"
        rows = conn.execute(
            f"""
            SELECT
              p.id, p.slug, p.name, p.name_short, p.acronym,
              p.price_cents, p.enabled,
              COALESCE(p.image_path, '/static/img/products/' || p.slug || '.png') AS image_path,
              p.icon,
              c.name AS category_name,
              c.sort_order AS category_sort_order,
              mp.sort_order AS menu_sort_order,
              p.sort_order AS product_sort_order
            FROM products p
            JOIN categories c ON c.id = p.category_id
            JOIN menu_products mp ON mp.product_id = p.id
            JOIN menus m ON m.id = mp.menu_id
            WHERE m.slug = ? {disabled_filter}
            ORDER BY c.sort_order, mp.sort_order, p.sort_order, p.name
            """,
            (menu,),
        )
        return rows_to_dicts(rows)


@router.get("/admin")
def list_products_admin() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
              p.*,
              COALESCE(p.image_path, '/static/img/products/' || p.slug || '.png') AS resolved_image_path,
              c.name AS category_name,
              COALESCE(group_concat(m.id), '') AS menu_ids,
              COALESCE(group_concat(m.name), '') AS menu_names
            FROM products p
            JOIN categories c ON c.id = p.category_id
            LEFT JOIN menu_products mp ON mp.product_id = p.id
            LEFT JOIN menus m ON m.id = mp.menu_id
            GROUP BY p.id
            ORDER BY c.sort_order, p.sort_order, p.name
            """
        )
        products = []
        for row in rows:
            item = dict(row)
            item["menu_ids"] = [int(v) for v in item["menu_ids"].split(",") if v]
            item["menu_names"] = [v for v in item["menu_names"].split(",") if v]
            products.append(item)
        return products


@router.get("/{product_id}")
def get_product(product_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *, COALESCE(image_path, '/static/img/products/' || slug || '.png') AS resolved_image_path
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        item = dict(row)
        item["menu_ids"] = [
            r["menu_id"] for r in conn.execute("SELECT menu_id FROM menu_products WHERE product_id = ? ORDER BY menu_id", (product_id,))
        ]
        return item


@router.post("")
def create_product(payload: ProductIn) -> dict:
    clean = _clean_product_payload(payload)
    with get_connection() as conn:
        category = conn.execute("SELECT id FROM categories WHERE id = ?", (clean["category_id"],)).fetchone()
        if category is None:
            raise HTTPException(status_code=400, detail="Unknown category")
        duplicate = conn.execute("SELECT id FROM products WHERE slug = ?", (clean["slug"],)).fetchone()
        if duplicate is not None:
            raise HTTPException(status_code=400, detail="Slug già usato")
        cur = conn.execute(
            """
            INSERT INTO products(category_id, slug, name, name_short, acronym, price_cents, enabled, icon, image_path, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean["category_id"], clean["slug"], clean["name"], clean["name_short"], clean["acronym"],
                clean["price_cents"], clean["enabled"], clean["icon"], clean["image_path"], clean["sort_order"],
            ),
        )
        product_id = int(cur.lastrowid)
        _replace_product_menus(conn, product_id, payload.menu_ids)
        return {"id": product_id}


@router.put("/{product_id}")
def update_product(product_id: int, payload: ProductIn) -> dict:
    clean = _clean_product_payload(payload)
    with get_connection() as conn:
        exists = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Product not found")
        duplicate = conn.execute("SELECT id FROM products WHERE slug = ? AND id <> ?", (clean["slug"], product_id)).fetchone()
        if duplicate is not None:
            raise HTTPException(status_code=400, detail="Slug già usato")
        conn.execute(
            """
            UPDATE products
            SET category_id = ?, slug = ?, name = ?, name_short = ?, acronym = ?,
                price_cents = ?, enabled = ?, icon = ?, image_path = ?, sort_order = ?
            WHERE id = ?
            """,
            (
                clean["category_id"], clean["slug"], clean["name"], clean["name_short"], clean["acronym"],
                clean["price_cents"], clean["enabled"], clean["icon"], clean["image_path"], clean["sort_order"], product_id,
            ),
        )
        _replace_product_menus(conn, product_id, payload.menu_ids)
        return {"ok": True}


@router.patch("/{product_id}/enabled")
def set_product_enabled(product_id: int, enabled: bool) -> dict:
    with get_connection() as conn:
        cur = conn.execute("UPDATE products SET enabled = ? WHERE id = ?", (int(enabled), product_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"ok": True}


def _replace_product_menus(conn, product_id: int, menu_ids: list[int]) -> None:
    conn.execute("DELETE FROM menu_products WHERE product_id = ?", (product_id,))
    clean_ids = sorted(set(int(v) for v in menu_ids))
    for menu_id in clean_ids:
        menu = conn.execute("SELECT id FROM menus WHERE id = ?", (menu_id,)).fetchone()
        if menu is None:
            raise HTTPException(status_code=400, detail=f"Unknown menu id: {menu_id}")
        next_sort = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 10 FROM menu_products WHERE menu_id = ?", (menu_id,)).fetchone()[0]
        conn.execute("INSERT INTO menu_products(menu_id, product_id, sort_order) VALUES (?, ?, ?)", (menu_id, product_id, next_sort))
