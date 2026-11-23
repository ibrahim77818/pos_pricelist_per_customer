/** @odoo-module */

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { isAutoCustomerPricelistEnabled, resolveCustomerPricelist } from "./utils";

patch(PosStore.prototype, {
    isAutoCustomerPricelistEnabled() {
        return isAutoCustomerPricelistEnabled(this.config);
    },
    resolveCustomerPricelist(partner) {
        return resolveCustomerPricelist(this.config, partner);
    },
    getReceiptHeaderData(order) {
        const data = super.getReceiptHeaderData(...arguments);
        if (
            order &&
            order.pricelist_id &&
            this.isAutoCustomerPricelistEnabled() &&
            this.config.receipt_show_pricelist
        ) {
            data.ppc_pricelist_name = order.pricelist_id.display_name || order.pricelist_id.name;
        }
        return data;
    },
});
