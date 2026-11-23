/** @odoo-module */

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";

/**
 * Everything needed to resolve a customer pricelist is already in memory
 * (partners carry `pos_assigned_pricelist_id`, `pricelists` holds the POS pricelists),
 * so resolution never triggers an RPC.
 */
patch(PosStore.prototype, {
    isAutoCustomerPricelistEnabled() {
        return Boolean(this.config && this.config.auto_customer_pricelist && this.config.use_pricelist);
    },
    getPricelistById(pricelistId) {
        if (!pricelistId) {
            return undefined;
        }
        return (this.pricelists || []).find((pricelist) => pricelist.id === pricelistId);
    },
    /**
     * @param {Object|null} partner
     * @returns {{pricelist: Object, source: 'customer'|'default'}}
     */
    resolveCustomerPricelist(partner) {
        const assigned = partner && partner.pos_assigned_pricelist_id;
        if (assigned) {
            // inactive / foreign-company pricelists are filtered server side,
            // pricelists not available in this POS are simply not loaded.
            const pricelist = this.getPricelistById(assigned[0]);
            if (pricelist) {
                return { pricelist, source: "customer" };
            }
        }
        return { pricelist: this.default_pricelist, source: "default" };
    },
    getReceiptHeaderData(order) {
        const data = super.getReceiptHeaderData(...arguments);
        if (
            order &&
            order.pricelist &&
            this.isAutoCustomerPricelistEnabled() &&
            this.config.receipt_show_pricelist
        ) {
            data.ppc_pricelist_name = order.pricelist.display_name || order.pricelist.name;
        }
        return data;
    },
});
