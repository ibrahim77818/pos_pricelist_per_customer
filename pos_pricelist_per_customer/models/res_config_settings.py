# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_auto_customer_pricelist = fields.Boolean(
        related='pos_config_id.auto_customer_pricelist', readonly=False)
    pos_receipt_show_pricelist = fields.Boolean(
        related='pos_config_id.receipt_show_pricelist', readonly=False)
