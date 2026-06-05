from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db.database import init_db
from app.routes import api_cashiers, api_meta, api_orders, api_printers, api_products, pages

app = FastAPI(title="Mugnozzo Sagra Manager 3.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(pages.router)
app.include_router(api_products.router)
app.include_router(api_cashiers.router)
app.include_router(api_meta.router)
app.include_router(api_orders.router)
app.include_router(api_printers.router)
