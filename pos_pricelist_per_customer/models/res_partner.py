# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    pos_assigned_pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Assigned Pricelist (POS)',
        compute='_compute_pos_assigned_pricelist_id',
        help="Pricelist explicitly assigned to this customer (or to its company) for the "
             "current company. Unlike the standard 'Pricelist' field, it ignores the generic "
             "fallback and country-group pricelists, and inactive pricelists.",
    )

    @api.depends_context('company')
    def _compute_pos_assigned_pricelist_id(self):
        """Batch-read explicit ``property_product_pricelist`` assignments.

        ``property_product_pricelist`` is computed in ``product`` and always returns a
        pricelist (the partner's own, a country-group one, or the first pricelist of the
        company). The POS must only switch pricelist when one was *explicitly* assigned,
        so we read the ``ir.property`` records directly: one query for the whole batch.
        """
        self.pos_assigned_pricelist_id = False
        partners = self.filtered(lambda p: p._origin.id)
        if not partners:
            return
        company = self.env.company
        partner_ids = set(partners._origin.ids) | set(partners._origin.commercial_partner_id.ids)
        field = self.env['ir.model.fields']._get('res.partner', 'property_product_pricelist')
        props = self.env['ir.property'].sudo().search([
            ('fields_id', '=', field.id),
            ('res_id', 'in', ['res.partner,%s' % pid for pid in partner_ids]),
            ('company_id', 'in', [company.id, False]),
        ])
        # company-specific values override company-less ones
        value_by_partner = {}
        for prop in props.sorted(lambda p: bool(p.company_id)):
            try:
                partner_id = int(prop.res_id.split(',')[1])
            except (AttributeError, IndexError, ValueError):
                continue
            pricelist_id = False
            if prop.value_reference:
                try:
                    model, res_id = prop.value_reference.split(',')
                    if model == 'product.pricelist':
                        pricelist_id = int(res_id)
                except ValueError:
                    pricelist_id = False
            value_by_partner[partner_id] = pricelist_id

        Pricelist = self.env['product.pricelist'].sudo().with_context(active_test=False)
        valid_ids = set(
            Pricelist.browse({pl for pl in value_by_partner.values() if pl}).exists().filtered(
                lambda pl: pl.active and pl.company_id in (company, self.env['res.company'])
            ).ids
        )
        for partner in partners:
            origin = partner._origin
            pricelist_id = value_by_partner.get(origin.id)
            if not pricelist_id and origin.commercial_partner_id != origin:
                pricelist_id = value_by_partner.get(origin.commercial_partner_id.id)
            partner.pos_assigned_pricelist_id = pricelist_id if pricelist_id in valid_ids else False
