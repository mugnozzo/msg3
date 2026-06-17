from __future__ import annotations

import socket
import threading
from pathlib import Path
from typing import Any

from app.db.database import DEFAULT_FILE_PRINTER_PATH, get_connection
from app.services import escpos

_printer_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_lock(printer_id: int) -> threading.Lock:
    with _locks_guard:
        if printer_id not in _printer_locks:
            _printer_locks[printer_id] = threading.Lock()
        return _printer_locks[printer_id]


def format_money(cents: int) -> str:
    #return f"€ {cents / 100:.2f}".replace(".", ",")
    return f"{cents / 100:.2f}".replace(",", ".")

def build_receipt_waiter(order: dict[str, Any], items: list[dict[str, Any]], copy_label: str) -> bytes:
    width = 48
    right = 7
    width_lg = 24
    out = bytearray()
    out += escpos.init()
    out += escpos.align("center")
    out += escpos.bold(True) + escpos.double_size(True)
    out += escpos.line("SAGRA DELL'OLIVA DOLCE")
    out += escpos.line(copy_label)
    out += escpos.line(f"Ordine #{order['order_number']}")
    out += escpos.line(order["created_at"])
    out += escpos.separator(width)
    out += escpos.align("left")
    for item in items:
        qty = item["quantity"]
        name = item["name_snapshot"]
        line = f"{qty}x {name}"
        out += escpos.line(f"{line}")
    out += escpos.separator(width_lg)
    out += escpos.line(f"{'TOTALE':<{width_lg-right}}{format_money(order['total_cents']):>{right}}")
    out += escpos.double_size(False) + escpos.bold(False)
    out += escpos.feed(6)
    out += escpos.cut()
    return bytes(out)


def build_receipt_client(order: dict[str, Any], items: list[dict[str, Any]], copy_label: str) -> bytes:
    width = 48
    right = 8
    width_lg = 24
    out = bytearray()
    out += escpos.init()
    out += escpos.align("center")
    out += escpos.bold(True) + escpos.double_size(True)
    out += escpos.line("SAGRA DELL'OLIVA DOLCE")
    out += escpos.line(copy_label)
    out += escpos.double_size(False) + escpos.bold(False)
    out += escpos.line(f"Ordine #{order['order_number']}")
    out += escpos.line(order["created_at"])
    out += escpos.separator(width)
    out += escpos.align("left")
    for item in items:
        qty = item["quantity"]
        name = item["name_snapshot"][:18]
        total = format_money(item["line_total_cents"])
        left = f"{qty}x {name}"
        out += escpos.line(f"{left:<{width-right}}{total:>{right}}")
    out += escpos.separator(width)
    out += escpos.bold(True)
    out += escpos.line(f"{'TOTALE':<{width-right}}{format_money(order['total_cents']):>{right}}")
    out += escpos.bold(False)
    out += escpos.feed(6)
    out += escpos.cut()
    return bytes(out)


def build_order_receipt(order_id: int) -> bytes:
    with get_connection() as conn:
        order = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())
        items = [dict(row) for row in conn.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,))]
    return build_receipt_client(order, items, "COPIA CLIENTE") + build_receipt_waiter(order, items, "COPIA CAMERIERE")


def send_to_printer(printer: dict[str, Any], data: bytes) -> None:
    kind = printer["kind"]
    address = printer["address"]
    if kind == "file":
        path = Path(address) if address else DEFAULT_FILE_PRINTER_PATH
        # Guard against old/bad config where the address is a directory, e.g. /mnt/data.
        if path.exists() and path.is_dir():
            path = path / "printer-output.bin"
        elif path.suffix == "":
            path = path / "printer-output.bin"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as f:
            f.write(data)
        return
    if kind == "usb":
        with open(address, "wb") as f:
            f.write(data)
        return
    if kind == "network":
        host, _, port_raw = address.partition(":")
        port = int(port_raw or "9100")
        with socket.create_connection((host, port), timeout=5) as sock:
            sock.sendall(data)
        return
    raise ValueError(f"Unsupported printer kind: {kind}")


def process_print_job(print_job_id: int) -> None:
    with get_connection() as conn:
        job = dict(conn.execute("SELECT * FROM print_jobs WHERE id = ?", (print_job_id,)).fetchone())
        printer = dict(conn.execute("SELECT * FROM printers WHERE id = ?", (job["printer_id"],)).fetchone())

    lock = _get_lock(printer["id"])
    with lock:
        attempt_id: int | None = None
        try:
            with get_connection() as conn:
                conn.execute("UPDATE print_jobs SET status = 'printing', attempt_count = attempt_count + 1 WHERE id = ?", (print_job_id,))
                cur = conn.execute("INSERT INTO print_job_attempts(print_job_id) VALUES (?)", (print_job_id,))
                attempt_id = cur.lastrowid

            data = build_order_receipt(job["order_id"])
            send_to_printer(printer, data)

            with get_connection() as conn:
                conn.execute("UPDATE print_jobs SET status = 'printed', printed_at = datetime('now'), error_message = NULL WHERE id = ?", (print_job_id,))
                conn.execute("UPDATE print_job_attempts SET finished_at = datetime('now'), success = 1 WHERE id = ?", (attempt_id,))
        except Exception as exc:
            message = str(exc)
            with get_connection() as conn:
                conn.execute("UPDATE print_jobs SET status = 'failed', error_message = ? WHERE id = ?", (message, print_job_id))
                if attempt_id is not None:
                    conn.execute("UPDATE print_job_attempts SET finished_at = datetime('now'), success = 0, error_message = ? WHERE id = ?", (message, attempt_id))
            raise


def create_and_process_print_job(order_id: int, printer_id: int) -> int:
    with get_connection() as conn:
        cur = conn.execute("INSERT INTO print_jobs(order_id, printer_id) VALUES (?, ?)", (order_id, printer_id))
        job_id = cur.lastrowid
    process_print_job(job_id)
    return int(job_id)
