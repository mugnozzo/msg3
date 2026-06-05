from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.db.database import get_connection, rows_to_dicts

router = APIRouter(prefix="/api/cashiers", tags=["cashiers"])


class CashierPayload(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    menu_id: int
    printer_id: int
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


def fetch_cashier(conn, cashier_id: int):
    return conn.execute(
        """
        SELECT
          c.id,
          c.name,
          c.enabled,
          cs.menu_id,
          m.slug AS menu_slug,
          m.name AS menu_name,
          cs.printer_id,
          p.name AS printer_name
        FROM cashiers c
        LEFT JOIN cashier_settings cs ON cs.cashier_id = c.id
        LEFT JOIN menus m ON m.id = cs.menu_id
        LEFT JOIN printers p ON p.id = cs.printer_id
        WHERE c.id = ?
        """,
        (cashier_id,),
    ).fetchone()


def validate_refs(conn, menu_id: int, printer_id: int) -> None:
    menu = conn.execute("SELECT id FROM menus WHERE id = ?", (menu_id,)).fetchone()
    if menu is None:
        raise HTTPException(status_code=400, detail="Menu not found")
    printer = conn.execute("SELECT id FROM printers WHERE id = ?", (printer_id,)).fetchone()
    if printer is None:
        raise HTTPException(status_code=400, detail="Printer not found")


@router.get("")
def list_cashiers() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
              c.id,
              c.name,
              c.enabled,
              cs.menu_id,
              m.slug AS menu_slug,
              m.name AS menu_name,
              cs.printer_id,
              p.name AS printer_name
            FROM cashiers c
            LEFT JOIN cashier_settings cs ON cs.cashier_id = c.id
            LEFT JOIN menus m ON m.id = cs.menu_id
            LEFT JOIN printers p ON p.id = cs.printer_id
            ORDER BY c.id
            """
        )
        return rows_to_dicts(rows)


@router.get("/{cashier_id}")
def get_cashier(cashier_id: int) -> dict:
    with get_connection() as conn:
        row = fetch_cashier(conn, cashier_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Cashier not found")
        return dict(row)


@router.post("")
def create_cashier(payload: CashierPayload) -> dict:
    try:
        with get_connection() as conn:
            validate_refs(conn, payload.menu_id, payload.printer_id)
            cur = conn.execute(
                "INSERT INTO cashiers(name, enabled) VALUES (?, ?)",
                (payload.name, int(payload.enabled)),
            )
            cashier_id = cur.lastrowid
            conn.execute(
                """
                INSERT INTO cashier_settings(cashier_id, printer_id, menu_id)
                VALUES (?, ?, ?)
                """,
                (cashier_id, payload.printer_id, payload.menu_id),
            )
            row = fetch_cashier(conn, int(cashier_id))
            return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=400, detail="A cashier with this name already exists") from exc
        raise


@router.put("/{cashier_id}")
def update_cashier(cashier_id: int, payload: CashierPayload) -> dict:
    try:
        with get_connection() as conn:
            existing = conn.execute("SELECT id FROM cashiers WHERE id = ?", (cashier_id,)).fetchone()
            if existing is None:
                raise HTTPException(status_code=404, detail="Cashier not found")
            validate_refs(conn, payload.menu_id, payload.printer_id)
            conn.execute(
                "UPDATE cashiers SET name = ?, enabled = ? WHERE id = ?",
                (payload.name, int(payload.enabled), cashier_id),
            )
            conn.execute(
                """
                INSERT INTO cashier_settings(cashier_id, printer_id, menu_id)
                VALUES (?, ?, ?)
                ON CONFLICT(cashier_id) DO UPDATE SET
                  printer_id = excluded.printer_id,
                  menu_id = excluded.menu_id
                """,
                (cashier_id, payload.printer_id, payload.menu_id),
            )
            row = fetch_cashier(conn, cashier_id)
            return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=400, detail="A cashier with this name already exists") from exc
        raise


@router.delete("/{cashier_id}")
def delete_cashier(cashier_id: int) -> dict:
    with get_connection() as conn:
        used = conn.execute("SELECT COUNT(*) FROM orders WHERE cashier_id = ?", (cashier_id,)).fetchone()[0]
        if used:
            conn.execute("UPDATE cashiers SET enabled = 0 WHERE id = ?", (cashier_id,))
            return {"status": "disabled", "reason": "Cashier already has orders, so it was disabled instead of deleted"}
        conn.execute("DELETE FROM cashier_settings WHERE cashier_id = ?", (cashier_id,))
        conn.execute("DELETE FROM cashiers WHERE id = ?", (cashier_id,))
        return {"status": "deleted"}
