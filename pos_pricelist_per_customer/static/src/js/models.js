/** @odoo-module */

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(Order.prototype, {
    _ppcEnabled() {
        return Boolean(this.pos?.isAutoCustomerPricelistEnabled?.());
    },
    /**
     * Lines whose price must never be recomputed from a pricelist. Core only reprices
     * lines with `price_type === "original"` (manual prices, refund lines and loyalty
     * rewards use "manual"/"automatic"); this also covers refund/reward lines created
     * by third-party code that left the type on "original".
     */
    _ppcSnapshotGuardedLines() {
        const guarded = [];
        for (const line of this.get_orderlines() || []) {
            if (line.price_type !== "original") {
                continue;
            }
            if (line.refunded_orderline_id || line.is_reward_line) {
                guarded.push([line, line.price]);
            }
        }
        return guarded;
    },
    _ppcRestoreGuardedLines(guarded) {
        for (const [line, price] of guarded) {
            if (line.price !== price) {
                line.price = price;
            }
        }
    },
    _ppcApplyPricelist(pricelist, source) {
        this._ppcSource = source;
        try {
            this.set_pricelist(pricelist);
        } finally {
            this._ppcSource = null;
        }
    },
    set_pricelist(pricelist) {
        if (!this._ppcEnabled()) {
            return super.set_pricelist(...arguments);
        }
        if (this._ppcForcedPricelist) {
            pricelist = this._ppcForcedPricelist;
        }
        const guarded = this._ppcSnapshotGuardedLines();
        const result = super.set_pricelist(pricelist);
        this._ppcRestoreGuardedLines(guarded);
        if (this._ppcSource) {
            this.pricelist_source = this._ppcSource;
        } else {
            const defaultPricelist = this.pos.default_pricelist;
            this.pricelist_source =
                pricelist && defaultPricelist && pricelist.id === defaultPricelist.id
                    ? "default"
                    : "manual";
        }
        return result;
    },
    /**
     * In Odoo 17 `set_partner()` calls this for every customer change (customer list,
     * payment screen, partner barcode, refunds). Core fiscal-position logic is kept;
     * only the pricelist it picks is replaced, so prices are recomputed once.
     */
    updatePricelistAndFiscalPosition(newPartner) {
        if (!this._ppcEnabled()) {
            return super.updatePricelistAndFiscalPosition(...arguments);
        }
        if (this.getHasRefundLines()) {
            // Refunds keep the pricelist and fiscal position of the refunded order
            // (see the TicketScreen patch); refund line prices are fixed anyway.
            return;
        }
        const { pricelist, source } = this.pos.resolveCustomerPricelist(newPartner);
        this._ppcForcedPricelist = pricelist;
        this._ppcSource = source;
        try {
            return super.updatePricelistAndFiscalPosition(...arguments);
        } finally {
            this._ppcForcedPricelist = null;
            this._ppcSource = null;
        }
    },
    /**
     * Use the pricelist of the refunded order for a pure refund order.
     * @param {Object|undefined} originalPricelist pricelist object of the refunded order
     */
    applyRefundPricelist(originalPricelist) {
        if (!this._ppcEnabled()) {
            return;
        }
        const lines = this.get_orderlines();
        if (!lines.length || !lines.every((line) => line.refunded_orderline_id)) {
            return; // mixed order: keep current pricelist to avoid repricing sale lines
        }
        const pricelist = originalPricelist && this.pos.getPricelistById(originalPricelist.id);
        if (pricelist) {
            this._ppcApplyPricelist(pricelist, "refund");
        } else {
            // not loaded here: backend sets the original pricelist on sync
            this.pricelist_source = "refund";
        }
    },
    getPricelistSourceLabel() {
        const labels = {
            default: _t("POS Default"),
            customer: _t("Customer Pricelist"),
            manual: _t("Manually Selected"),
            refund: _t("Refunded Order"),
        };
        return labels[this.pricelist_source] || "";
    },
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.pricelist_source = json.pricelist_source || false;
    },
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        if (this._ppcEnabled()) {
            json.pricelist_source = this.pricelist_source || false;
        }
        return json;
    },
});
