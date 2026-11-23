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

    @api.depends('specific_property_product_pricelist',
                 'commercial_partner_id.specific_property_product_pricelist')
    @api.depends_context('company')
    def _compute_pos_assigned_pricelist_id(self):
        """Explicit assignment only.

        Since Odoo 18 the customer's own pricelist is the company-dependent field
        ``specific_property_product_pricelist``; ``property_product_pricelist`` adds the
        country-group / first-pricelist fallback, which the POS must not apply.
        """
        company = self.env.company
        no_company = self.env['res.company']
        for partner in self:
            pricelist = partner.sudo().specific_property_product_pricelist
            commercial = partner.commercial_partner_id
            if not pricelist and commercial and commercial != partner:
                pricelist = commercial.sudo().specific_property_product_pricelist
            pricelist = pricelist.with_context(active_test=False).exists() if pricelist else pricelist
            if pricelist and (not pricelist.active or pricelist.company_id not in (company, no_company)):
                pricelist = False
            partner.pos_assigned_pricelist_id = pricelist.id if pricelist else False

    @api.model
    def _load_pos_data_fields(self, config):
        """Ship the explicit customer pricelist with the partners (initial load and
        partner search/reload) so the POS resolves the pricelist in memory."""
        fields_list = super()._load_pos_data_fields(config)
        if config and config._is_auto_customer_pricelist_active() \
                and 'pos_assigned_pricelist_id' not in fields_list:
            fields_list = list(fields_list) + ['pos_assigned_pricelist_id']
        return fields_list
