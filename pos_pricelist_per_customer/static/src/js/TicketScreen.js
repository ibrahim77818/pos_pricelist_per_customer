odoo.define('pos_pricelist_per_customer.TicketScreen', function (require) {
    'use strict';

    const TicketScreen = require('point_of_sale.TicketScreen');
    const Registries = require('point_of_sale.Registries');

    const PPCTicketScreen = (TicketScreen) =>
        class extends TicketScreen {
            /**
             * After core builds the refund order, give it the pricelist of the refunded order
             * instead of the customer's current pricelist.
             */
            async _onDoRefund() {
                const originalOrder = this.getSelectedSyncedOrder();
                const result = await super._onDoRefund(...arguments);
                if (!originalOrder || !this.env.pos.isAutoCustomerPricelistEnabled()) {
                    return result;
                }
                const destinationOrder = this.env.pos.get_order();
                if (!destinationOrder || !destinationOrder.getHasRefundLines()) {
                    return result;
                }
                const originalLineIds = new Set(originalOrder.get_orderlines().map((line) => line.id));
                const refundsOriginal = destinationOrder
                    .get_orderlines()
                    .some((line) => originalLineIds.has(line.refunded_orderline_id));
                if (refundsOriginal) {
                    destinationOrder.applyRefundPricelist(originalOrder.pricelist);
                }
                return result;
            }
        };
    Registries.Component.extend(TicketScreen, PPCTicketScreen);

    return PPCTicketScreen;
});
