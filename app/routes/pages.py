from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db.database import get_connection, rows_to_dicts

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def home() -> RedirectResponse:
    return RedirectResponse("/cashier/1")


@router.get("/cashier/{cashier_id:int}")
def cashier_by_id(request: Request, cashier_id: int):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
              c.id AS cashier_id,
              c.name AS cashier_name,
              c.enabled AS cashier_enabled,
              m.slug AS menu_slug,
              m.name AS menu_name,
              p.name AS printer_name
            FROM cashiers c
            JOIN cashier_settings cs ON cs.cashier_id = c.id
            JOIN menus m ON m.id = cs.menu_id
            JOIN printers p ON p.id = cs.printer_id
            WHERE c.id = ?
            """,
            (cashier_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Cashier not found or not configured")
    if not row["cashier_enabled"]:
        raise HTTPException(status_code=400, detail="Cashier is disabled")
    return templates.TemplateResponse("cashier.html", {"request": request, **dict(row)})


@router.get("/cashier/{menu_slug}")
def cashier_by_menu_slug(request: Request, menu_slug: str):
    # Backward-compatible development URL. Real cash desks should use /cashier/{id}.
    return templates.TemplateResponse(
        "cashier.html",
        {
            "request": request,
            "cashier_id": 1,
            "cashier_name": "Cassa 1",
            "menu_slug": menu_slug,
            "menu_name": menu_slug,
            "printer_name": "Stampante configurata per Cassa 1",
        },
    )


@router.get("/orders")
def orders_page(request: Request):
    return templates.TemplateResponse("orders.html", {"request": request})


@router.get("/printers/test")
def printers_test_page(request: Request):
    with get_connection() as conn:
        printers = rows_to_dicts(conn.execute("SELECT * FROM printers ORDER BY id"))
    return templates.TemplateResponse("printers.html", {"request": request, "printers": printers})


@router.get("/settings/products")
def settings_products_page(request: Request):
    return templates.TemplateResponse("settings_products.html", {"request": request})


@router.get("/settings/printers")
def settings_printers_page(request: Request):
    return templates.TemplateResponse("settings_printers.html", {"request": request})


@router.get("/settings/cashiers")
def settings_cashiers_page(request: Request):
    return templates.TemplateResponse("settings_cashiers.html", {"request": request})
