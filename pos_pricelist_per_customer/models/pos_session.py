# -*- coding: utf-8 -*-
from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_res_partner(self):
        """Ship the explicit customer pricelist with the partners so the POS resolves the
        pricelist in memory. Used by the initial load, the background partner load and
        ``get_pos_ui_res_partner_by_params`` (search / reload after edit)."""
        params = super()._loader_params_res_partner()
        if self.config_id._is_auto_customer_pricelist_active():
            fields_list = params['search_params'].setdefault('fields', [])
            if 'pos_assigned_pricelist_id' not in fields_list:
                fields_list.append('pos_assigned_pricelist_id')
        return params
