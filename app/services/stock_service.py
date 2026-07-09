from __future__ import annotations

import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.services.time_utils import current_rome_business_date, rome_day_bounds_for_db

SCALE = 1000


def decimal_to_milli(value: Any) -> int:
    if value is None or value == "":
        raise ValueError("Quantity is required")
    return int((Decimal(str(value).replace(",", ".")) * SCALE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def milli_to_decimal(value: int | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(int(value)) / SCALE)


def format_quantity_milli(value: int | None) -> str:
    if value is None:
        return "—"
    dec = Decimal(int(value)) / SCALE
    text = f"{dec:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def get_stock_status(conn: sqlite3.Connection, business_date: str | None = None) -> list[dict[str, Any]]:
    business_date = business_date or current_rome_business_date()
    day_start, day_end = rome_day_bounds_for_db(business_date)
    usage_rows = conn.execute(
        """
        SELECT
          si.id AS stock_item_id,
          COALESCE(SUM(CASE WHEN o.id IS NULL THEN 0 ELSE oi.quantity * psu.quantity_milli END), 0) AS consumed_milli
        FROM stock_items si
        LEFT JOIN product_stock_usages psu ON psu.stock_item_id = si.id
        LEFT JOIN order_items oi ON oi.product_id = psu.product_id
        LEFT JOIN orders o ON o.id = oi.order_id
         AND o.status = 'created'
         AND o.created_at >= ?
         AND o.created_at < ?
        GROUP BY si.id
        """,
        (day_start, day_end),
    ).fetchall()
    consumed_by_stock_id = {int(row["stock_item_id"]): int(row["consumed_milli"] or 0) for row in usage_rows}

    rows = conn.execute(
        """
        SELECT
          si.id,
          si.slug,
          si.name,
          si.unit_name,
          si.enabled,
          si.sort_order,
          sds.initial_quantity_milli,
          sds.warning_threshold_milli,
          sds.notes
        FROM stock_items si
        LEFT JOIN stock_day_settings sds
          ON sds.stock_item_id = si.id AND sds.business_date = ?
        WHERE si.enabled = 1
        ORDER BY si.sort_order, si.name
        """,
        (business_date,),
    ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        initial = item["initial_quantity_milli"]
        consumed = consumed_by_stock_id.get(int(item["id"]), 0)
        remaining = None if initial is None else int(initial) - consumed
        threshold = item["warning_threshold_milli"]
        if initial is None:
            status = "untracked"
        elif remaining < 0:
            status = "insufficient"
        elif threshold is not None and remaining <= int(threshold):
            status = "low"
        else:
            status = "ok"
        item.update({
            "business_date": business_date,
            "initial_quantity_milli": initial,
            "initial_quantity": milli_to_decimal(initial),
            "initial_quantity_display": format_quantity_milli(initial),
            "consumed_milli": consumed,
            "consumed": milli_to_decimal(consumed),
            "consumed_display": format_quantity_milli(consumed),
            "remaining_milli": remaining,
            "remaining": milli_to_decimal(remaining),
            "remaining_display": format_quantity_milli(remaining),
            "warning_threshold_milli": threshold,
            "warning_threshold": milli_to_decimal(threshold),
            "warning_threshold_display": format_quantity_milli(threshold),
            "status": status,
            "tracked": initial is not None,
        })
        result.append(item)
    return result


def get_order_stock_warnings(conn: sqlite3.Connection, quantities_by_product_id: dict[int, int]) -> list[dict[str, Any]]:
    if not quantities_by_product_id:
        return []
    product_ids = list(quantities_by_product_id)
    placeholders = ",".join("?" for _ in product_ids)
    rows = conn.execute(
        f"""
        SELECT
          si.id AS stock_item_id,
          si.slug,
          si.name,
          si.unit_name,
          psu.product_id,
          psu.quantity_milli,
          sds.initial_quantity_milli,
          sds.warning_threshold_milli
        FROM product_stock_usages psu
        JOIN stock_items si ON si.id = psu.stock_item_id AND si.enabled = 1
        LEFT JOIN stock_day_settings sds
          ON sds.stock_item_id = si.id AND sds.business_date = ?
        WHERE psu.product_id IN ({placeholders})
        """,
        (current_rome_business_date(), *product_ids),
    ).fetchall()
    if not rows:
        return []

    stock_status = {int(item["id"]): item for item in get_stock_status(conn)}
    requested_by_stock_id: dict[int, int] = {}
    meta_by_stock_id: dict[int, dict[str, Any]] = {}
    for row in rows:
        stock_id = int(row["stock_item_id"])
        requested_by_stock_id[stock_id] = requested_by_stock_id.get(stock_id, 0) + int(row["quantity_milli"]) * int(quantities_by_product_id[int(row["product_id"])])
        meta_by_stock_id[stock_id] = dict(row)

    warnings = []
    for stock_id, requested in requested_by_stock_id.items():
        current = stock_status.get(stock_id)
        if not current or not current["tracked"]:
            continue
        remaining_after = int(current["remaining_milli"]) - requested
        threshold = current["warning_threshold_milli"]
        if remaining_after < 0:
            status = "insufficient"
        elif threshold is not None and remaining_after <= int(threshold):
            status = "low"
        else:
            continue
        meta = meta_by_stock_id[stock_id]
        warnings.append({
            "stock_item_id": stock_id,
            "slug": meta["slug"],
            "name": meta["name"],
            "unit_name": meta["unit_name"],
            "status": status,
            "requested_milli": requested,
            "requested_display": format_quantity_milli(requested),
            "remaining_before_milli": current["remaining_milli"],
            "remaining_before_display": current["remaining_display"],
            "remaining_after_milli": remaining_after,
            "remaining_after_display": format_quantity_milli(remaining_after),
            "warning_threshold_milli": threshold,
            "warning_threshold_display": format_quantity_milli(threshold),
        })
    return warnings
