# POS Pricelist per Customer — Odoo 19.0

Applies each customer's assigned pricelist automatically in the Point of Sale, per POS, with no server call when a customer is selected. Shows the pricelist on screen and on the receipt, and stores it (with its source) on the order, refunds included. Community and Enterprise, English and Arabic.

## Branches

| Odoo version | Branch |
|---|---|
| 16.0 | [`16.0`](../../tree/16.0) |
| 17.0 | [`17.0`](../../tree/17.0) |
| 18.0 | [`18.0`](../../tree/18.0) |
| 19.0 | [`19.0`](../../tree/19.0) |
| 20.0 | [`20.0`](../../tree/20.0) |

This branch: **19.0**.

## Installation

1. Copy the `pos_pricelist_per_customer` folder into your addons path, or clone this branch:
   ```
   git clone -b 19.0 --single-branch https://github.com/ibrahim77818/pos_pricelist_per_customer.git
   ```
2. Restart Odoo, update the Apps list and install **POS Pricelist per Customer** (depends only on `point_of_sale`).
3. *Point of Sale › Configuration › Settings › Pricing*: enable **Flexible Pricelists**, then **Automatic Customer Pricelist** for each POS that should use it (off by default). **Show Pricelist on Receipt** is on by default.

## Behaviour (when enabled)

| Situation | Pricelist applied | Source stored |
|---|---|---|
| New order / no customer | POS default | `default` |
| Customer with an explicitly assigned pricelist available in the POS | Customer pricelist | `customer` |
| Customer without one, or with an archived, other-company or unavailable pricelist | POS default | `default` |
| Cashier picks a pricelist with the Pricelist button | That pricelist | `manual` |
| Refund | Pricelist of the refunded order | `refund` |
| Order preset with its own pricelist (Odoo 19.0 presets) | Preset pricelist | `preset` |

Manually typed prices and loyalty reward lines are never repriced. A contact inherits its company's pricelist. With the option off, standard Odoo behaviour is unchanged.

## Tests

```
odoo-bin -c <conf> -d <db> -i pos_pricelist_per_customer --test-tags /pos_pricelist_per_customer --stop-after-init
```

## Author & license

Ibrahim Yahia — [LinkedIn](https://www.linkedin.com/in/ibrahim-yahia) · ibrahim.yahiah@gmail.com · LGPL-3
