from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.database import get_connection, rows_to_dicts
from app.services.stock_service import decimal_to_milli, get_stock_status
from app.services.time_utils import current_rome_business_date

router = APIRouter(prefix="/api/stock", tags=["stock"])


class StockDaySettingIn(BaseModel):
    business_date: str | None = None
    initial_quantity: str | float | int | None = None
    warning_threshold: str | float | int | None = None
    notes: str | None = None


@router.get("/items")
def list_stock_items() -> list[dict]:
    with get_connection() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM stock_items ORDER BY sort_order, name"))


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
