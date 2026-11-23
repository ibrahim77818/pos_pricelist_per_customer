# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    auto_customer_pricelist = fields.Boolean(
        string='Automatic Customer Pricelist',
        default=False,
        help="When a customer is selected on an order, automatically apply the pricelist "
             "assigned to that customer (if it is available in this Point of Sale). "
             "Orders without a customer, or with a customer without an assigned pricelist, "
             "use the default pricelist of this Point of Sale.",
    )
    receipt_show_pricelist = fields.Boolean(
        string='Show Pricelist on Receipt',
        default=True,
        help="Print the pricelist applied to the order on the POS receipt "
             "(only when Automatic Customer Pricelist is enabled).",
    )

    def _is_auto_customer_pricelist_active(self):
        """The feature only makes sense with flexible pricelists enabled."""
        self.ensure_one()
        return bool(self.auto_customer_pricelist and self.use_pricelist)

    def _get_auto_customer_allowed_pricelists(self):
        """Pricelists the POS is allowed to apply (same set the session loads)."""
        self.ensure_one()
        if self.use_pricelist:
            return self.available_pricelist_ids | self.pricelist_id
        return self.pricelist_id
