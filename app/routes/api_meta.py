from __future__ import annotations

from fastapi import APIRouter

from app.db.database import get_connection, rows_to_dicts

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/categories")
def list_categories() -> list[dict]:
    with get_connection() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM categories ORDER BY sort_order, name"))


@router.get("/menus")
def list_menus() -> list[dict]:
    with get_connection() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM menus ORDER BY id"))
