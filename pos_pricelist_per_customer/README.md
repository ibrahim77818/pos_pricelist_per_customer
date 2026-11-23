# POS Pricelist per Customer (Odoo 16.0)

Applies the customer's assigned pricelist automatically in the Point of Sale. Works on Community and Enterprise. Ships with English and Arabic.

## Configuration
*Point of Sale › Configuration › Settings › Pricing.* Enable **Flexible Pricelists**, then **Automatic Customer Pricelist** (off by default). **Show Pricelist on Receipt** is on by default.

## Behaviour (when enabled)
| Situation | Pricelist applied | Source stored on the order |
|---|---|---|
| New order / no customer | POS default | `default` |
| Customer with an explicitly assigned pricelist that is available in the POS | Customer pricelist | `customer` |
| Customer without one, or with an inactive, other-company or unavailable pricelist | POS default | `default` |
| Customer removed from the order | POS default | `default` |
| Cashier picks a pricelist with the Pricelist button | That pricelist | `manual` |
| Refund order (all refund lines) | Pricelist of the refunded order | `refund` |

* Only explicitly assigned pricelists count. The generic fallback and country-group pricelists returned by the standard `property_product_pricelist` field are ignored. A contact inherits its company's assignment.
* Resolution runs in the browser from data loaded with the session (`pos_assigned_pricelist_id` is added to the partner loader). No RPC is made when a customer is selected.
* Manual line prices, refund lines and loyalty reward lines are never repriced. With `pos_loyalty`, rewards are recomputed through its own `set_pricelist` hook.
* Refunds keep the original pricelist and fiscal position. The backend enforces the original pricelist even if it is no longer loaded in the POS. Backend refunds (`Return Products`) are tagged `refund`.
* The current pricelist is shown under the Customer button (highlighted when it is the customer's own pricelist) and, optionally, on the receipt.
* When the option is disabled, the module does not change core behaviour.

## Tests
```
odoo-bin -c <conf> -d <db> -i pos_pricelist_per_customer --test-tags /pos_pricelist_per_customer --stop-after-init
```
The loyalty tests run only when `pos_loyalty` is installed and are skipped otherwise.
