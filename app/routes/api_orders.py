from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.database import get_connection, rows_to_dicts
from app.services.order_service import create_order
from app.services.print_service import create_and_process_print_job

router = APIRouter(prefix="/api/orders", tags=["orders"])


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int


class OrderIn(BaseModel):
    items: list[OrderItemIn]
    cashier_id: int = 1
    menu: str = "main"
    print_now: bool = True


@router.post("")
def create_order_endpoint(payload: OrderIn) -> dict:
    try:
        return create_order([item.model_dump() for item in payload.items], payload.cashier_id, payload.menu, payload.print_now)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def list_orders(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT o.*, c.name AS cashier_name, m.name AS menu_name
            FROM orders o
            LEFT JOIN cashiers c ON c.id = o.cashier_id
            LEFT JOIN menus m ON m.id = o.menu_id
            ORDER BY o.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return rows_to_dicts(rows)


@router.get("/{order_id}")
def get_order(order_id: int) -> dict:
    with get_connection() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        items = rows_to_dicts(conn.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)))
        jobs = rows_to_dicts(conn.execute("SELECT * FROM print_jobs WHERE order_id = ? ORDER BY id DESC", (order_id,)))
        return {"order": dict(order), "items": items, "print_jobs": jobs}


@router.post("/{order_id}/reprint")
def reprint_order(order_id: int) -> dict:
    with get_connection() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        setting = conn.execute("SELECT printer_id FROM cashier_settings WHERE cashier_id = ?", (order["cashier_id"],)).fetchone()
        printer_id = setting["printer_id"] if setting else 1
    try:
        job_id = create_and_process_print_job(order_id, int(printer_id))
        return {"order_id": order_id, "print_job_id": job_id, "status": "printed"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
