/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import {
    getAvailablePricelist,
    isAutoCustomerPricelistEnabled,
    resolveCustomerPricelist,
} from "./utils";

/**
 * `pricelist_source` is a pos.order field: since Odoo 18 the POS loads and syncs
 * order fields automatically, so no JSON import/export code is needed.
 */
patch(PosOrder.prototype, {
    _ppcEnabled() {
        return isAutoCustomerPricelistEnabled(this.config);
    },
    /**
     * Lines whose price must never be recomputed from a pricelist. Core only reprices
     * lines with `price_type === "original"` (manual prices, refund lines and loyalty
     * rewards use "manual"/"automatic"); this also covers refund/reward lines created
     * by third-party code that left the type on "original".
     */
    _ppcSnapshotGuardedLines() {
        const guarded = [];
        for (const line of this.lines || []) {
            if (line.price_type !== "original") {
                continue;
            }
            if (line.refunded_orderline_id || line.is_reward_line) {
                guarded.push([line, line.price_unit]);
            }
        }
        return guarded;
    },
    _ppcRestoreGuardedLines(guarded) {
        for (const [line, price] of guarded) {
            if (line.price_unit !== price) {
                line.price_unit = price;
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
            const defaultPricelist = this.config.pricelist_id;
            this.pricelist_source =
                pricelist && defaultPricelist && pricelist.id === defaultPricelist.id
                    ? "default"
                    : "manual";
        }
        return result;
    },
    /**
     * `set_partner()` calls this for every customer change (customer list, payment
     * screen, partner barcode, refunds). Core fiscal-position logic is kept; only the
     * pricelist it picks is replaced, so prices are recomputed once.
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
        const { pricelist, source } = resolveCustomerPricelist(this.config, newPartner);
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
     * @param {Object|undefined} originalPricelist pricelist record of the refunded order
     */
    applyRefundPricelist(originalPricelist) {
        if (!this._ppcEnabled()) {
            return;
        }
        const lines = this.lines || [];
        if (!lines.length || !lines.every((line) => line.refunded_orderline_id)) {
            return; // mixed order: keep current pricelist to avoid repricing sale lines
        }
        const pricelist = originalPricelist && getAvailablePricelist(this.config, originalPricelist.id);
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
});
