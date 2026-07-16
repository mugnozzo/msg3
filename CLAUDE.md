# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

MSG3 (Mugnozzo Sagra Gizmo) is a local-first point-of-sale and festival management system for Italian *sagre* (food festivals): cash desks, ESC/POS receipt printing, kitchen display screens, and stock tracking. It runs entirely on a local LAN with no cloud dependency, operated by volunteers with limited technical training. Simplicity and reliability are prioritized over feature completeness — avoid introducing frameworks, microservices, or abstractions the project doesn't already use.

## Commands

Setup:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp data/seed.sample.json data/seed.json   # first run only; seed.json is gitignored
```

Run (dev, with reload):
```bash
./scripts/run.sh
# or: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

There is no test suite, linter, or type-checker configured in this repo — don't assume `pytest`/`ruff`/`mypy` commands exist.

### Database

SQLite, auto-created on startup at `data/msg.sqlite3` (gitignored) by running `app/db/schema.sql` (idempotent `CREATE TABLE IF NOT EXISTS`) and seeding from `data/seed.json` (falls back to `data/seed.sample.json`) only if the `products` table is empty.

The project deliberately has **no migration framework**. The documented workflow for schema changes during development is: stop the server, delete `data/msg.sqlite3*`, edit `schema.sql`, restart. One-off scripts under `scripts/` (e.g. `scripts/migrate_001_stock_items.py`) exist only to patch already-deployed production databases without wiping data — write a new one in that style if you need to evolve a live DB, but don't build a general migration system.

## Architecture

**Stack:** FastAPI + raw `sqlite3` (no ORM) on the backend; server-rendered Jinja2 templates + vanilla JS/CSS on the frontend (no build step, no frontend framework).

**Request flow:** `app/main.py` registers one `APIRouter` per domain from `app/routes/`. Two kinds of routers:
- `pages.py` — renders Jinja2 templates from `app/templates/` for full pages (cashier UI, settings screens, kitchen display, stats, order history).
- `api_*.py` — JSON APIs consumed by the corresponding page's vanilla JS file in `app/static/js/` (e.g. `settings_products.html` + `settings-products.js` talk to `api_products.py`).

Route handlers open a connection with `get_connection()` (`app/db/database.py`), run raw SQL directly in the handler or a thin `app/services/` function, and return dicts (FastAPI serializes them; `rows_to_dicts()` converts `sqlite3.Row` results). There's no repository/DAO layer — SQL lives inline in routes and services.

**Domain model** (see `app/db/schema.sql`):
- `categories` → `products` → `menus`/`menu_products` (many-to-many): each cashier is bound to one menu via `cashier_settings`, which also holds its assigned `printer_id` and per-copy print flags.
- `orders` → `order_items`: items are snapshotted (`name_snapshot`, `price_cents_snapshot`) at order time so later product edits don't rewrite history.
- `print_jobs` → `print_job_attempts`: every print is queued as a job and recorded with attempt-level success/failure, so failed prints can be diagnosed/retried.
- `kitchen_screens` → `kitchen_screen_products`: filters which products appear on a given kitchen display (e.g. `/kitchen/grill`).
- `stock_items`, `product_stock_usages`, `stock_day_settings`: optional ingredient-level stock tracking. A product can consume fractional units of multiple stock items (`quantity_milli`, scaled ×1000 to avoid floats — see `SCALE` in `app/services/stock_service.py`). Stock is tracked **per business day** (`stock_day_settings`), not globally; an item with no row for the current date is "untracked" and produces no warnings. Business day boundaries are Europe/Rome calendar days, not UTC — always compute them via `time_utils.rome_day_bounds_for_db` / `current_rome_business_date`, never raw UTC date math.

**Services** (`app/services/`) hold logic shared across routes or that's non-trivial enough to not belong inline:
- `order_service.create_order` — validates items against the cashier's menu, computes totals, checks stock (`stock_service.get_order_stock_warnings`), inserts the order, and triggers printing. Stock warnings are informational only — orders are **never blocked** by low/insufficient stock; operators disable products manually if needed.
- `print_service` — builds ESC/POS receipt bytes (`build_receipt_client`/`build_receipt_waiter`, using raw command building via `app/services/escpos.py`, not a printing library) and sends them over `file`/`usb`/`network` (raw TCP :9100) transport based on `printers.kind`. Each printer has a dedicated `threading.Lock` (`_printer_locks`) so concurrent orders can't interleave writes to the same physical printer. Print jobs are tracked through explicit state transitions (`queued` → `printing` → `printed`/`failed`) persisted before/after the actual I/O, so a crash mid-print leaves an inspectable trail.
- `time_utils` — all receipt timestamps and business-date logic go through here; SQLite `datetime('now')` values are naive UTC strings and must be interpreted as such (see `parse_db_datetime`).

**Money** is always integer cents (`price_cents`, `total_cents`); never use floats for currency. **Stock quantities** are always integer "milli" units (`quantity_milli`, ×1000 scale); never use floats for stock math — convert via `stock_service.decimal_to_milli`/`milli_to_decimal` at the boundary only.

**Frontend:** each settings/feature page is a template + a matching standalone JS file that fetches its `api_*` router directly (no shared client-side framework or state store, no bundler — scripts are loaded as plain `<script>` tags). `app/templates/base.html` provides the shared nav/topbar shell that all pages extend.

**Product images** are excluded from the repo (`app/static/img/` is gitignored); the API falls back to `/static/img/products/<slug>.png` via `COALESCE(image_path, ...)` in SQL, and the frontend degrades to text-only if the image 404s.

**Locale:** UI strings, error messages returned to the frontend, and receipts are in Italian, matching the operator audience.
