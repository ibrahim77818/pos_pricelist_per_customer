/** @odoo-module */

import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";

patch(TicketScreen.prototype, {
    /**
     * Core hook, called once per refund order after its lines, fiscal position and
     * customer are set: give the refund the pricelist of the order it refunds instead
     * of the customer's current pricelist.
     */
    async addAdditionalRefundInfo(order, destinationOrder) {
        await super.addAdditionalRefundInfo(...arguments);
        if (!order || !destinationOrder || !destinationOrder._ppcEnabled()) {
            return;
        }
        if (destinationOrder.getHasRefundLines()) {
            destinationOrder.applyRefundPricelist(order.pricelist_id);
        }
    },
});
