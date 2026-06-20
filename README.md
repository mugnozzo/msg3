# MSG3 - Mugnozzo Sagra Gizmo

MSG3 is a lightweight local-first point-of-sale and festival management system designed for medium-sized Italian *sagre* and similar food events.

The project is optimized for simplicity, reliability, and ease of maintenance during real-world operation.

MSG3 is currently used in production environments with:

* 600-1000 visitors per day
* 30-40 products
* Multiple cash desks
* ESC/POS thermal printers
* Local-only network operation
* Volunteer operators with limited technical training

The system is intentionally simple and avoids unnecessary complexity.

---

# Features

## Sales Management

* Product categories
* Product images
* Fast touch-friendly interface
* Real-time cart
* Automatic totals calculation
* Order history
* Reprints

## Receipt Printing

* ESC/POS support
* USB printers
* Ethernet printers
* Multiple printers
* Per-cashier printer assignment
* Optional automatic paper cut
* Cashier name printed on receipts
* Europe/Rome timezone handling
* Configurable receipt copies

## Administration

* Product management
* Category management
* Printer management
* Cashier management
* Daily configuration
* Statistics and reports (ongoing development)

## Designed For

* Food festivals
* Temporary events
* Volunteer-operated cash desks
* Local networks without Internet access

---

# Technology Stack

## Backend

* Python 3
* FastAPI
* SQLite

## Frontend

* Vanilla HTML
* Vanilla JavaScript
* Vanilla CSS

No frontend framework is required.

## Printing

* ESC/POS
* Raw TCP printing
* Raw USB printing

No CUPS dependency is required.

---

# Architecture

MSG3 follows a very simple architecture:

```text
+------------------+
| Main Notebook    |
| Linux            |
| FastAPI Server   |
| Main Cash Desk   |
+--------+---------+
         |
         |
         v
+------------------+
| Local Network    |
+------------------+
         |
         +----------------+
         |                |
         v                v
+---------------+   +---------------+
| Cash Desk 2   |   | Bar           |
| Android       |   | Android       |
+---------------+   +---------------+
         |
         |
         |
         v
+---------------+
| Grill Display |
| Linux Laptop  |
+---------------+
```

The application is intended to run entirely on a private LAN.

No cloud services are required.

---

# Installation

## Requirements

* Python 3.11+ recommended
* Linux recommended
* Modern web browser

## Clone Repository

```bash
git clone <repository-url>
cd msg3
```

## Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## First Configuration

Create your own seed file:

```bash
cp data/seed.sample.json data/seed.json
```

Edit:

```text
data/seed.json
```

with your products and categories.

## Start Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The application will be available on the local network.

Example:

```text
http://192.168.1.10:8000
```

---

# Database

MSG3 uses SQLite.

The database is automatically created on startup.

Current development workflow assumes:

```text
Stop server
Delete database
Restart server
```

Because of this workflow:

* migrations are intentionally not used
* schema changes are applied directly
* seed data is recreated automatically

---

# Seed Data

Seed data is stored in JSON format.

Example files:

```text
data/
├── seed.sample.json
└── seed.json
```

## seed.sample.json

Version-controlled example configuration.

Should contain generic demonstration data only.

## seed.json

Local production configuration.

Contains:

* real products
* real prices
* real categories

This file should NOT be committed.

---

# Product Images

Product images are intentionally excluded from the repository.

Expected location:

```text
app/static/img/products/
```

Image naming convention:

```text
<product_slug>.png
```

Example:

```text
water.png
beer.png
cheeseburger.png
espresso.png
```

If an image is missing, the interface automatically falls back to a text-only representation.

Recommended image format:

* PNG
* Transparent background
* Square aspect ratio

Suggested size:

```text
256x256 px
```

or larger.

---

# Product Structure

Each product contains:

| Field       | Purpose            |
| ----------- | ------------------ |
| slug        | Stable identifier  |
| name        | Full product name  |
| name_short  | Short display name |
| acronym     | Compact identifier |
| price_cents | Price in cents     |
| sort_order  | Display order      |

Example:

```json
{
  "name": "Cheeseburger with Fries",
  "name_short": "Burger",
  "slug": "cheeseburger",
  "acronym": "BUR",
  "price_cents": 950
}
```

---

# Receipts

Receipts use:

```text
Europe/Rome
```

timezone.

Date format:

```text
dd/mm/yyyy hh:mm:ss
```

Example:

```text
21/06/2026 19:43:15
```

Receipts include:

* order number
* cashier name
* date/time
* products
* quantities
* totals

---

# Development Philosophy

MSG3 prioritizes:

1. Reliability
2. Simplicity
3. Maintainability
4. Offline operation

The project intentionally avoids:

* microservices
* cloud dependencies
* unnecessary frameworks
* overengineering

The goal is to have a system that can be understood and maintained by a small team of volunteers.

---

# Backup Strategy

Recommended:

```text
Backup SQLite database
+
Backup data/seed.json
+
Backup product images
```

before each event.

Automatic backup functionality may be added in future releases.

---

# Roadmap

Planned features include:

* Dynamic/manageable timezone
* Device/IP management
* Role-based permissions
* Product daily limits
* Sold-out handling
* Kitchen dashboards (to put screens with real-time orders in the kitchens)
* Internal messaging
* Popup notifications
* Print queue management
* Shared printer locking
* Partial and full voids
* Advanced statistics
* Automatic backups

---

# License

MSG3 is licensed under the GNU General Public License v3.0 (GPL-3.0).

You are free to use, study, modify, and redistribute this software under the terms of the GPL-3.0 license.

Any distributed modified version of MSG3 must also be released under the GPL-3.0 license and must provide access to the corresponding source code.

See the `LICENSE` file for the full license text.

Copyright (c) 2026 Alek Mugnozzo

---

# Acknowledgements

Built for real-world festival operations where speed, reliability and simplicity matter more than feature count.
