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
    def _ppc_refunded_pricelist(self, order):
        """Return the pricelist of the refunded order when *every* line sent for the order
        is a refund line coming from one single pricelist, else an empty recordset."""
        refunded_ids = []
        for line in order.get('lines') or []:
            if not isinstance(line, (list, tuple)) or len(line) < 3 or line[0] not in (0, 1):
                continue
            vals = line[2] if isinstance(line[2], dict) else {}
            refunded_ids.append(vals.get('refunded_orderline_id'))
        if not refunded_ids or not all(refunded_ids):
            return self.env['product.pricelist']
        pricelists = self.env['pos.order.line'].sudo().browse(refunded_ids).exists().order_id.pricelist_id
        return pricelists if len(pricelists) == 1 else self.env['product.pricelist']

    @api.model
    def _ppc_prepare_order_vals(self, order):
        """Sanitize the pricelist values sent by the POS (in place)."""
        valid_sources = dict(PRICELIST_SOURCES)
        if 'pricelist_source' in order and order['pricelist_source'] not in valid_sources:
            order['pricelist_source'] = False
        session = self.env['pos.session'].browse(order.get('session_id')).exists()
        config = session.config_id
        if not config or not config._is_auto_customer_pricelist_active():
            if 'pricelist_source' in order:
                order['pricelist_source'] = False
            return
        refund_pricelist = self._ppc_refunded_pricelist(order)
        if refund_pricelist:
            # A pure refund keeps the pricelist of the order it refunds, even when that
            # pricelist was not loaded in the POS (e.g. removed from the POS since).
            order['pricelist_id'] = refund_pricelist.id
            order['pricelist_source'] = 'refund'
        elif 'pricelist_id' in order:
            pricelist_id = order.get('pricelist_id')
            if not pricelist_id or not self.env['product.pricelist'].browse(pricelist_id).exists():
                order['pricelist_id'] = config.pricelist_id.id
                order['pricelist_source'] = 'default'

    @api.model
    def _process_order(self, order, existing_order):
        self._ppc_prepare_order_vals(order)
        return super()._process_order(order, existing_order)

    def _prepare_refund_values(self, current_session):
        values = super()._prepare_refund_values(current_session)
        if self.pricelist_source or current_session.config_id._is_auto_customer_pricelist_active():
            values['pricelist_source'] = 'refund'
        return values
