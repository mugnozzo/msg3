from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from app.db.database import get_connection, rows_to_dicts
from app.services.time_utils import APP_TIMEZONE, format_rome_datetime

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _parse_local_datetime(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.lower() == "now":
        return datetime.now(APP_TIMEZONE)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Data/ora non valida: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=APP_TIMEZONE)
    else:
        parsed = parsed.astimezone(APP_TIMEZONE)
    if end_of_day and parsed.time() == time.min and "T" not in value and " " not in value:
        parsed = parsed + timedelta(days=1)
    return parsed


def _to_db_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _build_filters(
    start: str | None,
    end: str | None,
    q: str | None,
    category_id: int | None,
    product_id: int | None,
    cashier_id: int | None,
    menu_id: int | None,
) -> tuple[str, list[object], dict[str, str | None]]:
    start_local = _parse_local_datetime(start)
    end_local = _parse_local_datetime(end, end_of_day=True)
    if start_local and end_local and start_local >= end_local:
        raise HTTPException(status_code=400, detail="La data/ora di inizio deve essere precedente alla fine")

    clauses = ["o.status = 'created'"]
    params: list[object] = []

    start_db = _to_db_datetime(start_local)
    end_db = _to_db_datetime(end_local)
    if start_db:
        clauses.append("o.created_at >= ?")
        params.append(start_db)
    if end_db:
        clauses.append("o.created_at < ?")
        params.append(end_db)

    search = (q or "").strip().lower()
    if search:
        clauses.append(
            """
            (
              lower(oi.name_snapshot) LIKE ?
              OR lower(COALESCE(p.name, '')) LIKE ?
              OR lower(COALESCE(p.name_short, '')) LIKE ?
              OR lower(COALESCE(p.slug, '')) LIKE ?
              OR lower(COALESCE(p.acronym, '')) LIKE ?
              OR lower(COALESCE(c.name, '')) LIKE ?
            )
            """
        )
        like = f"%{search}%"
        params.extend([like, like, like, like, like, like])

    if category_id:
        clauses.append("c.id = ?")
        params.append(category_id)
    if product_id:
        clauses.append("p.id = ?")
        params.append(product_id)
    if cashier_id:
        clauses.append("o.cashier_id = ?")
        params.append(cashier_id)
    if menu_id:
        clauses.append("o.menu_id = ?")
        params.append(menu_id)

    return " AND ".join(clauses), params, {
        "start_display": format_rome_datetime(start_db),
        "end_display": format_rome_datetime(end_db),
    }


@router.get("")
def get_stats(
    start: str | None = None,
    end: str | None = Query(default="now"),
    q: str | None = None,
    category_id: int | None = None,
    product_id: int | None = None,
    cashier_id: int | None = None,
    menu_id: int | None = None,
    group_by: str = Query(default="day", pattern="^(none|day|hour|cashier|category)$"),
) -> dict:
    where_sql, params, labels = _build_filters(start, end, q, category_id, product_id, cashier_id, menu_id)

    group_exprs = {
        "day": "date(datetime(o.created_at, 'localtime'))",
        "hour": "strftime('%Y-%m-%d %H:00', datetime(o.created_at, 'localtime'))",
        "cashier": "COALESCE(ca.name, 'Senza cassa')",
        "category": "COALESCE(c.name, 'Senza categoria')",
    }

    with get_connection() as conn:
        summary = dict(conn.execute(
            f"""
            SELECT
              COUNT(DISTINCT o.id) AS order_count,
              COALESCE(SUM(oi.quantity), 0) AS item_count,
              COALESCE(SUM(oi.line_total_cents), 0) AS total_cents
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            LEFT JOIN products p ON p.id = oi.product_id
            LEFT JOIN categories c ON c.id = p.category_id
            LEFT JOIN cashiers ca ON ca.id = o.cashier_id
            LEFT JOIN menus m ON m.id = o.menu_id
            WHERE {where_sql}
            """,
            params,
        ).fetchone())

        product_rows = rows_to_dicts(conn.execute(
            f"""
            SELECT
              p.id AS product_id,
              COALESCE(p.slug, '') AS slug,
              COALESCE(p.name, oi.name_snapshot) AS product_name,
              COALESCE(p.name_short, oi.name_snapshot) AS product_name_short,
              COALESCE(c.id, 0) AS category_id,
              COALESCE(c.name, 'Senza categoria') AS category_name,
              COALESCE(SUM(oi.quantity), 0) AS quantity,
              COALESCE(SUM(oi.line_total_cents), 0) AS total_cents,
              CASE WHEN SUM(oi.quantity) > 0 THEN ROUND(1.0 * SUM(oi.line_total_cents) / SUM(oi.quantity)) ELSE 0 END AS avg_price_cents
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            LEFT JOIN products p ON p.id = oi.product_id
            LEFT JOIN categories c ON c.id = p.category_id
            LEFT JOIN cashiers ca ON ca.id = o.cashier_id
            LEFT JOIN menus m ON m.id = o.menu_id
            WHERE {where_sql}
            GROUP BY p.id, oi.name_snapshot
            ORDER BY c.sort_order, p.sort_order, product_name
            """,
            params,
        ))

        groups: list[dict] = []
        if group_by != "none":
            expr = group_exprs[group_by]
            groups = rows_to_dicts(conn.execute(
                f"""
                SELECT
                  {expr} AS label,
                  COUNT(DISTINCT o.id) AS order_count,
                  COALESCE(SUM(oi.quantity), 0) AS item_count,
                  COALESCE(SUM(oi.line_total_cents), 0) AS total_cents
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                LEFT JOIN products p ON p.id = oi.product_id
                LEFT JOIN categories c ON c.id = p.category_id
                LEFT JOIN cashiers ca ON ca.id = o.cashier_id
                LEFT JOIN menus m ON m.id = o.menu_id
                WHERE {where_sql}
                GROUP BY label
                ORDER BY label DESC
                """,
                params,
            ))

    return {
        "filters": {"start": start, "end": end, "q": q, "category_id": category_id, "product_id": product_id, "cashier_id": cashier_id, "menu_id": menu_id, "group_by": group_by, **labels},
        "summary": summary,
        "groups": groups,
        "products": product_rows,
    }


@router.get("/filters")
def get_stats_filters() -> dict:
    with get_connection() as conn:
        return {
            "categories": rows_to_dicts(conn.execute("SELECT id, name FROM categories ORDER BY sort_order, name")),
            "products": rows_to_dicts(conn.execute("SELECT id, name, slug, category_id FROM products ORDER BY sort_order, name")),
            "cashiers": rows_to_dicts(conn.execute("SELECT id, name FROM cashiers ORDER BY id")),
            "menus": rows_to_dicts(conn.execute("SELECT id, name, slug FROM menus ORDER BY id")),
        }
