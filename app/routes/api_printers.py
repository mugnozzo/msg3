from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.db.database import DEFAULT_FILE_PRINTER_PATH, get_connection, rows_to_dicts
from app.services.print_service import send_to_printer
from app.services import escpos

router = APIRouter(prefix="/api/printers", tags=["printers"])

PrinterKind = Literal["file", "usb", "network"]


class PrinterPayload(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: PrinterKind
    address: str = Field(default="", max_length=300)
    enabled: bool = True

    @field_validator("name", "address")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


def normalize_address(kind: str, address: str) -> str:
    address = address.strip()
    if kind == "file":
        return address or str(DEFAULT_FILE_PRINTER_PATH)
    if kind == "usb":
        if not address:
            raise HTTPException(status_code=400, detail="USB printers need a device path, for example /dev/usb/lp0")
        return address
    if kind == "network":
        if not address:
            raise HTTPException(status_code=400, detail="Network printers need host:port, for example 192.168.1.50:9100")
        return address
    raise HTTPException(status_code=400, detail="Invalid printer type")


@router.get("")
def list_printers() -> list[dict]:
    with get_connection() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM printers ORDER BY id"))


@router.post("")
def create_printer(payload: PrinterPayload) -> dict:
    address = normalize_address(payload.kind, payload.address)
    try:
        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO printers(name, kind, address, enabled)
                VALUES (?, ?, ?, ?)
                """,
                (payload.name, payload.kind, address, int(payload.enabled)),
            )
            printer_id = cur.lastrowid
            row = conn.execute("SELECT * FROM printers WHERE id = ?", (printer_id,)).fetchone()
            return dict(row)
    except Exception as exc:
        message = str(exc)
        if "UNIQUE" in message.upper():
            raise HTTPException(status_code=400, detail="A printer with this name already exists") from exc
        raise


@router.put("/{printer_id}")
def update_printer(printer_id: int, payload: PrinterPayload) -> dict:
    address = normalize_address(payload.kind, payload.address)
    try:
        with get_connection() as conn:
            existing = conn.execute("SELECT id FROM printers WHERE id = ?", (printer_id,)).fetchone()
            if existing is None:
                raise HTTPException(status_code=404, detail="Printer not found")
            conn.execute(
                """
                UPDATE printers
                SET name = ?, kind = ?, address = ?, enabled = ?
                WHERE id = ?
                """,
                (payload.name, payload.kind, address, int(payload.enabled), printer_id),
            )
            row = conn.execute("SELECT * FROM printers WHERE id = ?", (printer_id,)).fetchone()
            return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        message = str(exc)
        if "UNIQUE" in message.upper():
            raise HTTPException(status_code=400, detail="A printer with this name already exists") from exc
        raise


@router.delete("/{printer_id}")
def delete_printer(printer_id: int) -> dict:
    with get_connection() as conn:
        used = conn.execute("SELECT COUNT(*) FROM print_jobs WHERE printer_id = ?", (printer_id,)).fetchone()[0]
        assigned = conn.execute("SELECT COUNT(*) FROM cashier_settings WHERE printer_id = ?", (printer_id,)).fetchone()[0]
        if used or assigned:
            conn.execute("UPDATE printers SET enabled = 0 WHERE id = ?", (printer_id,))
            return {"status": "disabled", "reason": "Printer is used by orders/cashiers, so it was disabled instead of deleted"}
        conn.execute("DELETE FROM printers WHERE id = ?", (printer_id,))
        return {"status": "deleted"}


@router.post("/{printer_id}/test")
def test_printer(printer_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM printers WHERE id = ?", (printer_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Printer not found")
        printer = dict(row)
    if not printer["enabled"]:
        raise HTTPException(status_code=400, detail="Printer is disabled")

    data = (
        escpos.init()
        + escpos.align("center")
        + escpos.bold(True)
        + escpos.line("MSG 3.0")
        + escpos.bold(False)
        + escpos.line("Test stampante")
        + escpos.line(printer["name"])
        + escpos.line(f"Tipo: {printer['kind']}")
        + escpos.line(f"\n\n\n")
        + escpos.feed(3)
        + escpos.cut()
    )
    try:
        send_to_printer(printer, data)
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
