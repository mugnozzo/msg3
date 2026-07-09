from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.database import get_connection, rows_to_dicts
from app.services.stock_service import decimal_to_milli, get_stock_status, milli_to_decimal, format_quantity_milli
from app.services.time_utils import current_rome_business_date

router = APIRouter(prefix="/api/stock", tags=["stock"])

_SLUG_RE = re.compile(r"^[a-z0-9_]+$")


class StockItemIn(BaseModel):
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    unit_name: str = Field(default="unità", min_length=1)
    enabled: bool = True
    sort_order: int = 0


class ProductStockUsageIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: str | float | int = Field(default=1)


class StockUsagesIn(BaseModel):
    usages: list[ProductStockUsageIn] = []


class StockDaySettingIn(BaseModel):
    business_date: str | None = None
    initial_quantity: str | float | int | None = None
    warning_threshold: str | float | int | None = None
    notes: str | None = None


def _clean_stock_payload(payload: StockItemIn) -> dict:
    slug = payload.slug.strip().lower().replace("-", "_")
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=400, detail="Slug non valido: usa solo lettere minuscole, numeri e underscore")
    return {
        "slug": slug,
        "name": payload.name.strip(),
        "unit_name": payload.unit_name.strip() or "unità",
        "enabled": int(payload.enabled),
        "sort_order": int(payload.sort_order),
    }


def _stock_item_row(conn, stock_item_id: int):
    return conn.execute("SELECT * FROM stock_items WHERE id = ?", (stock_item_id,)).fetchone()


@router.get("/items")
def list_stock_items(include_disabled: bool = True) -> list[dict]:
    with get_connection() as conn:
        disabled_filter = "" if include_disabled else "WHERE si.enabled = 1"
        rows = conn.execute(
            f"""
            SELECT
              si.*,
              COUNT(DISTINCT psu.product_id) AS usage_count,
              COUNT(DISTINCT sds.business_date) AS configured_days
            FROM stock_items si
            LEFT JOIN product_stock_usages psu ON psu.stock_item_id = si.id
            LEFT JOIN stock_day_settings sds ON sds.stock_item_id = si.id
            {disabled_filter}
            GROUP BY si.id
            ORDER BY si.sort_order, si.name
            """
        )
        return rows_to_dicts(rows)


@router.post("/items")
def create_stock_item(payload: StockItemIn) -> dict:
    clean = _clean_stock_payload(payload)
    with get_connection() as conn:
        duplicate = conn.execute("SELECT id FROM stock_items WHERE slug = ?", (clean["slug"],)).fetchone()
        if duplicate is not None:
            raise HTTPException(status_code=400, detail="Slug già usato")
        cur = conn.execute(
            """
            INSERT INTO stock_items(slug, name, unit_name, enabled, sort_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            (clean["slug"], clean["name"], clean["unit_name"], clean["enabled"], clean["sort_order"]),
        )
        return {"id": int(cur.lastrowid)}


@router.put("/items/{stock_item_id:int}")
def update_stock_item(stock_item_id: int, payload: StockItemIn) -> dict:
    clean = _clean_stock_payload(payload)
    with get_connection() as conn:
        exists = _stock_item_row(conn, stock_item_id)
        if exists is None:
            raise HTTPException(status_code=404, detail="Stock item not found")
        duplicate = conn.execute(
            "SELECT id FROM stock_items WHERE slug = ? AND id <> ?",
            (clean["slug"], stock_item_id),
        ).fetchone()
        if duplicate is not None:
            raise HTTPException(status_code=400, detail="Slug già usato")
        conn.execute(
            """
            UPDATE stock_items
            SET slug = ?, name = ?, unit_name = ?, enabled = ?, sort_order = ?
            WHERE id = ?
            """,
            (clean["slug"], clean["name"], clean["unit_name"], clean["enabled"], clean["sort_order"], stock_item_id),
        )
        return {"ok": True}


@router.patch("/items/{stock_item_id:int}/enabled")
def set_stock_item_enabled(stock_item_id: int, enabled: bool) -> dict:
    with get_connection() as conn:
        cur = conn.execute("UPDATE stock_items SET enabled = ? WHERE id = ?", (int(enabled), stock_item_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Stock item not found")
        return {"ok": True}


@router.delete("/items/{stock_item_id:int}")
def delete_stock_item(stock_item_id: int) -> dict:
    """Delete only unused stock definitions. Historical nightly settings are intentionally protected."""
    with get_connection() as conn:
        exists = _stock_item_row(conn, stock_item_id)
        if exists is None:
            raise HTTPException(status_code=404, detail="Stock item not found")
        usage_count = conn.execute(
            "SELECT COUNT(*) FROM product_stock_usages WHERE stock_item_id = ?",
            (stock_item_id,),
        ).fetchone()[0]
        day_count = conn.execute(
            "SELECT COUNT(*) FROM stock_day_settings WHERE stock_item_id = ?",
            (stock_item_id,),
        ).fetchone()[0]
        if usage_count or day_count:
            raise HTTPException(
                status_code=400,
                detail="Impossibile eliminare: lo stock ha associazioni prodotto o storico. Disattivalo invece.",
            )
        conn.execute("DELETE FROM stock_items WHERE id = ?", (stock_item_id,))
        return {"ok": True}


@router.get("/items/{stock_item_id:int}/usages")
def get_stock_item_usages(stock_item_id: int) -> list[dict]:
    with get_connection() as conn:
        if _stock_item_row(conn, stock_item_id) is None:
            raise HTTPException(status_code=404, detail="Stock item not found")
        rows = conn.execute(
            """
            SELECT
              psu.product_id,
              p.slug AS product_slug,
              p.name AS product_name,
              p.name_short AS product_name_short,
              psu.quantity_milli
            FROM product_stock_usages psu
            JOIN products p ON p.id = psu.product_id
            WHERE psu.stock_item_id = ?
            ORDER BY p.sort_order, p.name
            """,
            (stock_item_id,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["quantity"] = milli_to_decimal(item["quantity_milli"])
            item["quantity_display"] = format_quantity_milli(item["quantity_milli"])
            result.append(item)
        return result


@router.put("/items/{stock_item_id:int}/usages")
def replace_stock_item_usages(stock_item_id: int, payload: StockUsagesIn) -> dict:
    with get_connection() as conn:
        if _stock_item_row(conn, stock_item_id) is None:
            raise HTTPException(status_code=404, detail="Stock item not found")
        clean_usages: dict[int, int] = {}
        for usage in payload.usages:
            product_id = int(usage.product_id)
            product = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
            if product is None:
                raise HTTPException(status_code=400, detail=f"Prodotto non trovato: {product_id}")
            quantity_milli = decimal_to_milli(usage.quantity)
            if quantity_milli <= 0:
                raise HTTPException(status_code=400, detail="La quantità consumata deve essere maggiore di zero")
            clean_usages[product_id] = quantity_milli
        conn.execute("DELETE FROM product_stock_usages WHERE stock_item_id = ?", (stock_item_id,))
        for product_id, quantity_milli in sorted(clean_usages.items()):
            conn.execute(
                """
                INSERT INTO product_stock_usages(product_id, stock_item_id, quantity_milli)
                VALUES (?, ?, ?)
                """,
                (product_id, stock_item_id, quantity_milli),
            )
        return {"ok": True}


@router.get("/status")
def stock_status(business_date: str | None = None) -> dict:
    with get_connection() as conn:
        date = business_date or current_rome_business_date()
        return {"business_date": date, "items": get_stock_status(conn, date)}


@router.put("/items/{stock_item_id:int}/day")
def set_stock_day_setting(stock_item_id: int, payload: StockDaySettingIn) -> dict:
    business_date = payload.business_date or current_rome_business_date()
    initial_milli = None if payload.initial_quantity in (None, "") else decimal_to_milli(payload.initial_quantity)
    threshold_milli = None if payload.warning_threshold in (None, "") else decimal_to_milli(payload.warning_threshold)
    with get_connection() as conn:
        exists = conn.execute("SELECT id FROM stock_items WHERE id = ?", (stock_item_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Stock item not found")
        conn.execute(
            """
            INSERT INTO stock_day_settings(stock_item_id, business_date, initial_quantity_milli, warning_threshold_milli, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(stock_item_id, business_date) DO UPDATE SET
              initial_quantity_milli = excluded.initial_quantity_milli,
              warning_threshold_milli = excluded.warning_threshold_milli,
              notes = excluded.notes
            """,
            (stock_item_id, business_date, initial_milli, threshold_milli, payload.notes),
        )
        return {"ok": True, "business_date": business_date}


@router.delete("/items/{stock_item_id:int}/day/{business_date}")
def delete_stock_day_setting(stock_item_id: int, business_date: str) -> dict:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM stock_day_settings WHERE stock_item_id = ? AND business_date = ?",
            (stock_item_id, business_date),
        )
        return {"ok": True}


@router.get("/history")
def stock_history(limit: int = Query(default=20, ge=1, le=200)) -> list[dict]:
    with get_connection() as conn:
        dates = [
            row["business_date"]
            for row in conn.execute(
                "SELECT DISTINCT business_date FROM stock_day_settings ORDER BY business_date DESC LIMIT ?",
                (limit,),
            )
        ]
        return [{"business_date": date, "items": get_stock_status(conn, date)} for date in dates]
