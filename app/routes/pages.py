from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db.database import get_connection, rows_to_dicts

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def home() -> RedirectResponse:
    return RedirectResponse("/cashier/main")


@router.get("/cashier/{menu_slug}")
def cashier(request: Request, menu_slug: str):
    return templates.TemplateResponse("cashier.html", {"request": request, "menu_slug": menu_slug})


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
