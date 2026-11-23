/** @odoo-module */

import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";
import { patch } from "@web/core/utils/patch";

/**
 * Since Odoo 20 receipts are QWeb templates (receipt/ folder, shared by backend and
 * POS) rendered from the data built here; the header template reads
 * `extra_data.ppc_pricelist_name` (see views/pos_order_receipt_templates.xml).
 */
patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        if (this.order?.ppcShowPricelistOnReceipt && data?.extra_data) {
            data.extra_data.ppc_pricelist_name =
                this.order.pricelist_id.display_name || this.order.pricelist_id.name;
        }
        return data;
    },
});
