# -*- coding: utf-8 -*-
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged('post_install', '-at_install')
class TestPosPricelistPerCustomer(TestPoSCommon):
    """Backend side of pos_pricelist_per_customer.

    Pricelist resolution itself runs in the POS browser client; these TransactionCase tests
    cover everything it relies on and everything persisted: configuration defaults, the
    explicit customer pricelist shipped to the POS, the session loader, and how orders,
    refunds and loyalty reward lines are stored.
    """

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        Pricelist = cls.env['product.pricelist']
        currency = cls.company_currency
        cls.default_pricelist = cls.currency_pricelist
        cls.vip_pricelist = Pricelist.create({
            'name': 'VIP -10%',
            'currency_id': currency.id,
            'company_id': cls.company.id,
            'item_ids': [(0, 0, {
                'applied_on': '3_global',
                'compute_price': 'percentage',
                'percent_price': 10.0,
            })],
        })
        cls.wholesale_pricelist = Pricelist.create({
            'name': 'Wholesale -20%',
            'currency_id': currency.id,
            'item_ids': [(0, 0, {
                'applied_on': '3_global',
                'compute_price': 'percentage',
                'percent_price': 20.0,
            })],
        })
        # exists but is not offered in the POS
        cls.unavailable_pricelist = Pricelist.create({
            'name': 'Not in POS',
            'currency_id': currency.id,
        })

        cls.config = cls.basic_config
        cls.config.write({
            'use_pricelist': True,
            'pricelist_id': cls.default_pricelist.id,
            'available_pricelist_ids': [(6, 0, (cls.default_pricelist | cls.vip_pricelist
                                                | cls.wholesale_pricelist).ids)],
        })

        cls.product_a = cls.create_product('PPC Product A', cls.categ_basic, 100.0)
        cls.product_b = cls.create_product('PPC Product B', cls.categ_basic, 50.0)

        Partner = cls.env['res.partner']
        cls.vip_customer = Partner.create({'name': 'VIP Customer'})
        cls.vip_customer.property_product_pricelist = cls.vip_pricelist
        cls.plain_customer = Partner.create({'name': 'Customer Without Pricelist'})
        cls.unavailable_customer = Partner.create({'name': 'Customer With Unavailable Pricelist'})
        cls.unavailable_customer.property_product_pricelist = cls.unavailable_pricelist

    # ------------------------------------------------------------------ helpers
    def _enable(self, enabled=True):
        self.config.auto_customer_pricelist = enabled

    def _order_data(self, lines, customer=False, pricelist=None, source=None):
        """Build a POS UI order payload priced with ``pricelist`` (POS default if None).

        :param lines: list of ``(product, qty)`` or ``(product, qty, extra_vals)`` where
            ``extra_vals`` are written on the line (e.g. a manual ``price_unit``).
        """
        pricelist = pricelist or self.config.pricelist_id
        self.pricelist = pricelist  # used by create_ui_order_data to price the lines
        data = self.create_ui_order_data([(line[0], line[1]) for line in lines], customer=customer)
        for line_cmd, spec in zip(data['lines'], lines):
            extra = spec[2] if len(spec) > 2 else {}
            line_cmd[2].update(extra)
            if 'price_unit' in extra:
                subtotal = line_cmd[2]['price_unit'] * line_cmd[2]['qty']
                line_cmd[2].update(price_subtotal=subtotal, price_subtotal_incl=subtotal)
        data['pricelist_id'] = pricelist.id
        if source is not None:
            data['pricelist_source'] = source
        self._recompute_totals(data)
        return data

    def _recompute_totals(self, data):
        order = data
        total = sum(cmd[2]['price_subtotal_incl'] for cmd in order['lines'])
        base = sum(cmd[2]['price_subtotal'] for cmd in order['lines'])
        order.update(amount_total=total, amount_tax=total - base, amount_paid=total)
        order['payment_ids'] = order['payment_ids'][:1]
        order['payment_ids'][0][2]['amount'] = total

    def _sync(self, data):
        self.env['pos.order'].sync_from_ui([data])
        # the result may also contain the refunded order: look the order up by uuid
        return self.env['pos.order'].search([('uuid', '=', data['uuid'])], limit=1)

    # ------------------------------------------------------------ configuration
    def test_01_default_is_disabled(self):
        defaults = self.env['pos.config'].default_get(['auto_customer_pricelist', 'receipt_show_pricelist'])
        self.assertFalse(defaults.get('auto_customer_pricelist'))
        self.assertTrue(defaults.get('receipt_show_pricelist'))
        config = self.config  # created by TestPoSCommon, never toggled
        self.assertFalse(config.auto_customer_pricelist)
        self.assertTrue(config.receipt_show_pricelist)
        self.assertFalse(config._is_auto_customer_pricelist_active())
        settings = self.env['res.config.settings'].create({'pos_config_id': config.id})
        self.assertFalse(settings.pos_auto_customer_pricelist)

    def test_02_settings_write_through(self):
        settings = self.env['res.config.settings'].create({'pos_config_id': self.config.id})
        settings.pos_auto_customer_pricelist = True
        settings.pos_receipt_show_pricelist = False
        self.assertTrue(self.config.auto_customer_pricelist)
        self.assertFalse(self.config.receipt_show_pricelist)

    def test_03_requires_flexible_pricelists(self):
        self._enable()
        self.assertTrue(self.config._is_auto_customer_pricelist_active())
        self.config.use_pricelist = False
        self.assertFalse(self.config._is_auto_customer_pricelist_active())

    def test_04_loader_ships_field_only_when_enabled(self):
        Partner = self.env['res.partner']
        fields_disabled = Partner._load_pos_data_fields(self.config)
        self.assertNotIn('pos_assigned_pricelist_id', fields_disabled)
        self._enable()
        fields_enabled = Partner._load_pos_data_fields(self.config)
        self.assertIn('pos_assigned_pricelist_id', fields_enabled)
        # core fields untouched and no duplicates on repeated calls
        self.assertIn('property_product_pricelist', fields_enabled)
        fields_again = Partner._load_pos_data_fields(self.config)
        self.assertEqual(fields_again.count('pos_assigned_pricelist_id'), 1)

    def test_05_partner_reload_returns_assigned_pricelist(self):
        self._enable()
        partners = self.vip_customer | self.plain_customer
        fields_list = self.env['res.partner']._load_pos_data_fields(self.config)
        records = self.env['res.partner'].search_read([('id', 'in', partners.ids)], fields_list, load=False)
        by_id = {rec['id']: rec for rec in records}
        self.assertEqual(by_id[self.vip_customer.id]['pos_assigned_pricelist_id'], self.vip_pricelist.id)
        self.assertFalse(by_id[self.plain_customer.id]['pos_assigned_pricelist_id'])

    # --------------------------------------------------- customer pricelist data
    def test_10_customer_with_pricelist(self):
        self.assertEqual(self.vip_customer.pos_assigned_pricelist_id, self.vip_pricelist)

    def test_11_customer_without_pricelist_ignores_fallback(self):
        # the standard field always answers something (fallback / first pricelist) ...
        self.assertFalse(self.plain_customer.pos_assigned_pricelist_id)
        # ... and only an explicit assignment counts
        self.plain_customer.property_product_pricelist = self.wholesale_pricelist
        self.plain_customer.invalidate_recordset(['pos_assigned_pricelist_id'])
        self.assertEqual(self.plain_customer.pos_assigned_pricelist_id, self.wholesale_pricelist)

    def test_12_contact_inherits_company_pricelist(self):
        company = self.env['res.partner'].create({'name': 'PPC Corp', 'is_company': True})
        company.property_product_pricelist = self.wholesale_pricelist
        contact = self.env['res.partner'].create({'name': 'PPC Contact', 'parent_id': company.id})
        self.assertEqual(contact.pos_assigned_pricelist_id, self.wholesale_pricelist)

    def test_13_inactive_pricelist_is_ignored(self):
        archived = self.env['product.pricelist'].create({
            'name': 'Archived', 'currency_id': self.company_currency.id})
        customer = self.env['res.partner'].create({'name': 'Archived PL Customer'})
        customer.property_product_pricelist = archived
        self.assertEqual(customer.pos_assigned_pricelist_id, archived)
        archived.active = False
        customer.invalidate_recordset(['pos_assigned_pricelist_id'])
        self.assertFalse(customer.pos_assigned_pricelist_id)

    def test_14_other_company_pricelist_is_ignored(self):
        other_company = self.env['res.company'].create({'name': 'PPC Other Company'})
        foreign = self.env['product.pricelist'].create({
            'name': 'Foreign', 'currency_id': self.company_currency.id, 'company_id': other_company.id})
        customer = self.env['res.partner'].create({'name': 'Foreign PL Customer'})
        customer.property_product_pricelist = foreign
        customer.invalidate_recordset(['pos_assigned_pricelist_id'])
        self.assertFalse(customer.pos_assigned_pricelist_id)

    def test_15_pricelist_not_available_in_pos(self):
        """Assigned but not offered by the POS: shipped as data, never loaded as a POS
        pricelist, so the client falls back to the default pricelist."""
        self._enable()
        self.assertEqual(self.unavailable_customer.pos_assigned_pricelist_id, self.unavailable_pricelist)
        allowed = self.config._get_auto_customer_allowed_pricelists()
        self.assertNotIn(self.unavailable_pricelist, allowed)
        self.assertNotIn(self.unavailable_pricelist, self.config.available_pricelist_ids)
        self.assertIn(self.vip_pricelist, self.config.available_pricelist_ids)

    def test_16_batch_compute(self):
        partners = self.vip_customer | self.plain_customer | self.unavailable_customer
        partners.invalidate_recordset(['pos_assigned_pricelist_id'])
        self.assertEqual(
            partners.mapped(lambda p: p.pos_assigned_pricelist_id.id),
            [self.vip_pricelist.id, False, self.unavailable_pricelist.id])

    # ---------------------------------------------------------- order persistence
    def test_20_disabled_keeps_core_behaviour(self):
        self.open_new_session()
        data = self._order_data([(self.product_a, 1)], customer=self.vip_customer,
                                pricelist=self.vip_pricelist, source='customer')
        order = self._sync(data)
        self.assertEqual(order.pricelist_id, self.vip_pricelist)
        self.assertFalse(order.pricelist_source)

    def test_21_customer_pricelist_persisted(self):
        self._enable()
        self.open_new_session()
        data = self._order_data([(self.product_a, 2), (self.product_b, 1)],
                                customer=self.vip_customer, pricelist=self.vip_pricelist, source='customer')
        order = self._sync(data)
        self.assertEqual(order.pricelist_id, self.vip_pricelist)
        self.assertEqual(order.pricelist_source, 'customer')
        prices = {line.product_id: line.price_unit for line in order.lines}
        self.assertAlmostEqual(prices[self.product_a], 90.0)
        self.assertAlmostEqual(prices[self.product_b], 45.0)
        self.assertAlmostEqual(order.amount_total, 225.0)
        self.assertEqual(order.state, 'paid')

    def test_22_customer_without_pricelist_uses_default(self):
        self._enable()
        self.open_new_session()
        data = self._order_data([(self.product_a, 1)], customer=self.plain_customer, source='default')
        order = self._sync(data)
        self.assertEqual(order.pricelist_id, self.default_pricelist)
        self.assertEqual(order.pricelist_source, 'default')
        self.assertAlmostEqual(order.amount_total, 100.0)

    def test_23_no_customer_uses_default(self):
        self._enable()
        self.open_new_session()
        order = self._sync(self._order_data([(self.product_a, 1)], source='default'))
        self.assertEqual(order.pricelist_id, self.default_pricelist)
        self.assertEqual(order.pricelist_source, 'default')

    def test_24_manual_line_price_is_kept(self):
        """A line with a manual price keeps it, other lines follow the customer pricelist."""
        self._enable()
        self.open_new_session()
        data = self._order_data(
            [(self.product_a, 1), (self.product_b, 2, {'price_unit': 30.0, 'price_type': 'manual'})],
            customer=self.vip_customer, pricelist=self.vip_pricelist, source='customer')
        order = self._sync(data)
        prices = {line.product_id: line.price_unit for line in order.lines}
        self.assertAlmostEqual(prices[self.product_a], 90.0)
        self.assertAlmostEqual(prices[self.product_b], 30.0)
        self.assertAlmostEqual(order.amount_total, 150.0)

    def test_25_manual_pricelist_source(self):
        self._enable()
        self.open_new_session()
        data = self._order_data([(self.product_a, 1)], customer=self.plain_customer,
                                pricelist=self.wholesale_pricelist, source='manual')
        order = self._sync(data)
        self.assertEqual(order.pricelist_id, self.wholesale_pricelist)
        self.assertEqual(order.pricelist_source, 'manual')

    def test_25b_preset_source_is_kept(self):
        self._enable()
        self.open_new_session()
        order = self._sync(self._order_data([(self.product_a, 1)], pricelist=self.wholesale_pricelist, source='preset'))
        self.assertEqual(order.pricelist_id, self.wholesale_pricelist)
        self.assertEqual(order.pricelist_source, 'preset')

    def test_26_unknown_source_is_dropped(self):
        self._enable()
        self.open_new_session()
        order = self._sync(self._order_data([(self.product_a, 1)], source='hacked'))
        self.assertFalse(order.pricelist_source)

    def test_27_deleted_pricelist_falls_back_to_default(self):
        self._enable()
        self.open_new_session()
        temp = self.env['product.pricelist'].create({'name': 'Temp', 'currency_id': self.company_currency.id})
        data = self._order_data([(self.product_a, 1)], source='customer')
        data['pricelist_id'] = temp.id
        temp.unlink()
        order = self._sync(data)
        self.assertEqual(order.pricelist_id, self.default_pricelist)
        self.assertEqual(order.pricelist_source, 'default')

    def test_28_read_pos_data(self):
        self._enable()
        self.open_new_session()
        order = self._sync(self._order_data([(self.product_a, 1)], customer=self.vip_customer,
                                            pricelist=self.vip_pricelist, source='customer'))
        exported = order.read_pos_data([], self.config)['pos.order'][0]
        self.assertEqual(exported['pricelist_source'], 'customer')
        self.assertEqual(exported['pricelist_id'], self.vip_pricelist.id)

    # ----------------------------------------------------------------- refunds
    def _make_vip_order(self):
        return self._sync(self._order_data([(self.product_a, 2)], customer=self.vip_customer,
                                           pricelist=self.vip_pricelist, source='customer'))

    def test_30_pos_refund_keeps_original_pricelist(self):
        """The customer's pricelist changed since the sale: the refund still carries the
        pricelist of the refunded order."""
        self._enable()
        self.open_new_session()
        original = self._make_vip_order()
        self.vip_customer.property_product_pricelist = self.wholesale_pricelist
        original_line = original.lines[0]
        data = self._order_data(
            [(self.product_a, -1, {'price_unit': original_line.price_unit,
                                   'refunded_orderline_id': original_line.id,
                                   'price_type': 'automatic'})],
            customer=self.vip_customer, pricelist=self.wholesale_pricelist, source='customer')
        refund = self._sync(data)
        self.assertEqual(refund.pricelist_id, self.vip_pricelist)
        self.assertEqual(refund.pricelist_source, 'refund')
        self.assertEqual(refund.refunded_order_id, original)
        self.assertAlmostEqual(refund.amount_total, -90.0)
        self.assertAlmostEqual(original_line.refunded_qty, 1.0)

    def test_31_mixed_refund_and_sale_keeps_ui_pricelist(self):
        self._enable()
        self.open_new_session()
        original = self._make_vip_order()
        original_line = original.lines[0]
        data = self._order_data(
            [(self.product_a, -1, {'price_unit': original_line.price_unit,
                                   'refunded_orderline_id': original_line.id}),
             (self.product_b, 1)],
            customer=self.plain_customer, source='default')
        order = self._sync(data)
        self.assertEqual(order.pricelist_id, self.default_pricelist)
        self.assertEqual(order.pricelist_source, 'default')

    def test_32_backend_refund(self):
        self._enable()
        self.open_new_session()
        original = self._make_vip_order()
        action = original.refund()
        refund = self.env['pos.order'].browse(action['res_id'])
        self.assertEqual(refund.pricelist_id, self.vip_pricelist)
        self.assertEqual(refund.pricelist_source, 'refund')
        self.assertTrue(all(qty < 0 for qty in refund.lines.mapped('qty')))

    def test_33_backend_refund_feature_disabled(self):
        self.open_new_session()
        original = self._make_vip_order()
        refund = self.env['pos.order'].browse(original.refund()['res_id'])
        self.assertEqual(refund.pricelist_id, self.vip_pricelist)
        self.assertFalse(refund.pricelist_source)

    # ------------------------------------------------------------ loyalty
    def _pos_loyalty_installed(self):
        return bool(self.env['ir.module.module'].search(
            [('name', '=', 'pos_loyalty'), ('state', '=', 'installed')], limit=1))

    def test_40_loyalty_reward_line_untouched(self):
        """A promotion reward line synced with a customer-pricelist order keeps its amount,
        the order total stays consistent and the pricelist/source are stored."""
        if not self._pos_loyalty_installed():
            self.skipTest('pos_loyalty is not installed')
        self._enable()
        program = self.env['loyalty.program'].create({
            'name': 'PPC 10% on order',
            'program_type': 'promotion',
            'trigger': 'auto',
            'applies_on': 'current',
            'pos_ok': True,
            'pos_config_ids': [(6, 0, self.config.ids)],
            'rule_ids': [(0, 0, {'minimum_qty': 1, 'reward_point_mode': 'order', 'reward_point_amount': 1})],
            'reward_ids': [(0, 0, {
                'reward_type': 'discount',
                'discount': 10,
                'discount_mode': 'percent',
                'discount_applicability': 'order',
                'required_points': 1,
            })],
        })
        reward = program.reward_ids
        self.assertTrue(reward.discount_line_product_id)
        self.open_new_session()
        # 2 x 90 (VIP) = 180, promotion 10% => -18
        data = self._order_data([(self.product_a, 2)], customer=self.vip_customer,
                                pricelist=self.vip_pricelist, source='customer')
        data['lines'].append((0, 0, {
            'id': 999001,
            'product_id': reward.discount_line_product_id.id,
            'qty': 1,
            'price_unit': -18.0,
            'price_subtotal': -18.0,
            'price_subtotal_incl': -18.0,
            'discount': 0.0,
            'tax_ids': [(6, 0, [])],
            'pack_lot_ids': [],
            'is_reward_line': True,
            'reward_id': reward.id,
            'reward_identifier_code': 'ppc-reward-1',
            'points_cost': 1,
            'price_type': 'automatic',
        }))
        self._recompute_totals(data)
        order = self._sync(data)
        self.assertEqual(order.pricelist_id, self.vip_pricelist)
        self.assertEqual(order.pricelist_source, 'customer')
        reward_line = order.lines.filtered('is_reward_line')
        self.assertEqual(len(reward_line), 1)
        self.assertEqual(reward_line.reward_id, reward)
        self.assertAlmostEqual(reward_line.price_unit, -18.0)
        self.assertAlmostEqual(order.amount_total, 162.0)
        self.assertEqual(order.state, 'paid')

    def test_41_loyalty_refund_with_reward_line(self):
        if not self._pos_loyalty_installed():
            self.skipTest('pos_loyalty is not installed')
        self._enable()
        self.open_new_session()
        original = self._make_vip_order()
        line = original.lines[0]
        data = self._order_data(
            [(self.product_a, -2, {'price_unit': line.price_unit, 'refunded_orderline_id': line.id,
                                   'price_type': 'automatic'})],
            customer=self.vip_customer, pricelist=self.default_pricelist, source='customer')
        refund = self._sync(data)
        self.assertEqual(refund.pricelist_id, self.vip_pricelist)
        self.assertEqual(refund.pricelist_source, 'refund')
        self.assertAlmostEqual(refund.amount_total, -180.0)
