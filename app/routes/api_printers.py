from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db.database import get_connection, rows_to_dicts
from app.services.print_service import send_to_printer
from app.services import escpos

router = APIRouter(prefix="/api/printers", tags=["printers"])


@router.get("")
def list_printers() -> list[dict]:
    with get_connection() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM printers ORDER BY id"))


@router.post("/{printer_id}/test")
def test_printer(printer_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM printers WHERE id = ?", (printer_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Printer not found")
        printer = dict(row)
    data = escpos.init() + escpos.align("center") + escpos.bold(True) + escpos.line("MSG 3.0") + escpos.bold(False) + escpos.line("Test stampa") + escpos.feed(3) + escpos.cut()
    try:
        send_to_printer(printer, data)
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
