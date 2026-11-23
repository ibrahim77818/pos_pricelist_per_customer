# -*- coding: utf-8 -*-
from odoo import api, fields, models

PRICELIST_SOURCES = [
    ('default', 'POS Default'),
    ('customer', 'Customer Pricelist'),
    ('manual', 'Manually Selected'),
    ('refund', 'Refunded Order'),
]


class PosOrder(models.Model):
    _inherit = 'pos.order'

    pricelist_source = fields.Selection(
        PRICELIST_SOURCES,
        string='Pricelist Source',
        readonly=True,
        copy=False,
        help="How the pricelist of this order was chosen in the Point of Sale.",
    )

    @api.model
    def _ppc_refunded_pricelist(self, ui_order):
        """Return the pricelist of the refunded order when *every* line of the UI order is a
        refund line coming from one single pricelist, else an empty recordset."""
        lines = ui_order.get('lines') or []
        refunded_ids = []
        for line in lines:
            vals = line[2] if isinstance(line, (list, tuple)) and len(line) > 2 else {}
            refunded_ids.append(isinstance(vals, dict) and vals.get('refunded_orderline_id'))
        if not refunded_ids or not all(refunded_ids):
            return self.env['product.pricelist']
        pricelists = self.env['pos.order.line'].sudo().browse(refunded_ids).exists().order_id.pricelist_id
        return pricelists if len(pricelists) == 1 else self.env['product.pricelist']

    @api.model
    def _order_fields(self, ui_order):
        vals = super()._order_fields(ui_order)
        session = self.env['pos.session'].browse(ui_order.get('pos_session_id')).exists()
        config = session.config_id
        if not config or not config._is_auto_customer_pricelist_active():
            return vals

        valid_sources = dict(PRICELIST_SOURCES)
        source = ui_order.get('pricelist_source')
        source = source if source in valid_sources else False

        refund_pricelist = self._ppc_refunded_pricelist(ui_order)
        if refund_pricelist:
            # A pure refund keeps the pricelist of the order it refunds, even when that
            # pricelist was not loaded in the POS (e.g. removed from the POS since).
            vals['pricelist_id'] = refund_pricelist.id
            source = 'refund'
        elif not vals.get('pricelist_id') or not self.env['product.pricelist'].browse(
                vals['pricelist_id']).exists():
            vals['pricelist_id'] = config.pricelist_id.id
            source = 'default'

        vals['pricelist_source'] = source or False
        return vals

    def _export_for_ui(self, order):
        result = super()._export_for_ui(order)
        result['pricelist_source'] = order.pricelist_source
        return result

    def _prepare_refund_values(self, current_session):
        values = super()._prepare_refund_values(current_session)
        if self.pricelist_source or current_session.config_id._is_auto_customer_pricelist_active():
            values['pricelist_source'] = 'refund'
        return values
