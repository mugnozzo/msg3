# MSG 3.0 prototype

First vertical slice for Mugnozzo Sagra Manager 3.0.

## Stack

- FastAPI
- SQLite
- Jinja templates
- Vanilla HTML/CSS/JS
- Raw ESC/POS bytes

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./scripts/run.sh
```

Open:

- `http://localhost:8000/cashier/1`
- `http://localhost:8000/cashier/main`
- `http://localhost:8000/cashier/bar`
- `http://localhost:8000/orders`
- `http://localhost:8000/printers/test`
- `http://localhost:8000/settings/products`
- `http://localhost:8000/settings/printers`
- `http://localhost:8000/settings/cashiers`

## Printer safety

The default printer is a fake file printer. It writes ESC/POS bytes to:

```text
data/printer-output.bin
```

This allows testing without sending bytes to a real printer.

Later printer examples:

```text
kind=usb      address=/dev/usb/lp0
kind=network  address=192.168.1.50:9100
```

## Current scope

Implemented:

- product management panel
- product menu assignment
- enable/disable products
- dynamic menu product grid
- cart
- change calculator
- SQLite schema and seed data
- order creation with product name/price snapshots
- two receipt copies per print job
- printer locking per backend process
- reprint endpoint/page
- test printer page
- printer management panel
- cashier management panel
- cashier-specific URLs like `/cashier/1`
- cashier menu/printer assignment

Not implemented yet:

- product daily limits
- running-out alerts
- kitchen dashboard
- full statistics dashboard


## Notes

Database and fake printer paths are anchored to the project root:

```text
msg3/data/msg.sqlite3
msg3/data/printer-output.bin
```

So they no longer depend on the directory from which `uvicorn` is launched.

## Printer management

Open:

```text
/settings/printers
```

Supported printer kinds:

- `file`: safe test output. Empty address uses `data/printer-output.bin`.
- `usb`: raw ESC/POS bytes to a device path, for example `/dev/usb/lp0`.
- `network`: raw ESC/POS bytes to `host:port`, usually `192.168.1.50:9100`.

Use the test button before assigning a real printer to a cashier.


## Cashier management

Open:

```text
/settings/cashiers
```

Each cashier has:

- name
- assigned menu
- assigned printer
- enabled/disabled state

The normal cashier URLs are now:

```text
/cashier/1
/cashier/2
```

The old development URLs still work:

```text
/cashier/main
/cashier/bar
```

but real cash desks should use the cashier ID URLs.
