# -*- coding: utf-8 -*-
{
    'name': 'POS Pricelist per Customer',
    'version': '17.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Automatically apply the customer assigned pricelist in the Point of Sale, '
               'with clean fallback to the POS default pricelist.',
    'description': """
POS Pricelist per Customer
==========================
* Per-POS switch (default off) to apply the customer's explicitly assigned pricelist
  when a customer is selected, and revert to the POS default pricelist otherwise.
* Resolution runs fully in the browser from data loaded with the session (no RPC per click).
* Ignores fallback / country-group pricelists, inactive pricelists and pricelists that are
  not available in the POS.
* Keeps manual prices, refund lines and loyalty reward lines untouched.
* Refunds keep the pricelist of the refunded order.
* Applied pricelist and its source are shown in the POS, on the receipt and stored on the order.
* Works on Community and Enterprise. English and Arabic.
    """,
    'author': 'Ibrahim Yahia',
    'website': 'https://www.linkedin.com/in/ibrahim-yahia',
    'depends': ['point_of_sale'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/pos_order_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_pricelist_per_customer/static/src/css/pos_pricelist_per_customer.css',
            'pos_pricelist_per_customer/static/src/js/**/*',
            'pos_pricelist_per_customer/static/src/xml/**/*',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
