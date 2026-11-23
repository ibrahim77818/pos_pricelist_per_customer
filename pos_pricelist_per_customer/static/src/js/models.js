odoo.define('pos_pricelist_per_customer.models', function (require) {
    'use strict';

    const { PosGlobalState, Order } = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');
    const core = require('web.core');
    const _t = core._t;

    /**
     * Global state: everything needed to resolve a customer pricelist is already in memory
     * (partners carry `pos_assigned_pricelist_id`, `pricelists` holds the POS pricelists),
     * so resolution never triggers an RPC.
     */
    const PPCPosGlobalState = (PosGlobalState) =>
        class extends PosGlobalState {
            isAutoCustomerPricelistEnabled() {
                return Boolean(this.config && this.config.auto_customer_pricelist && this.config.use_pricelist);
            }
            getPricelistById(pricelistId) {
                if (!pricelistId) {
                    return undefined;
                }
                return (this.pricelists || []).find((pricelist) => pricelist.id === pricelistId);
            }
            /**
             * @param {Object|null} partner
             * @returns {{pricelist: Object, source: 'customer'|'default'}}
             */
            resolveCustomerPricelist(partner) {
                const assigned = partner && partner.pos_assigned_pricelist_id;
                if (assigned) {
                    // inactive / foreign-company pricelists are already filtered server side,
                    // pricelists not available in this POS are simply not loaded.
                    const pricelist = this.getPricelistById(assigned[0]);
                    if (pricelist) {
                        return { pricelist, source: 'customer' };
                    }
                }
                return { pricelist: this.default_pricelist, source: 'default' };
            }
        };
    Registries.Model.extend(PosGlobalState, PPCPosGlobalState);

    const PPCOrder = (Order) =>
        class extends Order {
            _ppcEnabled() {
                return Boolean(this.pos && this.pos.isAutoCustomerPricelistEnabled && this.pos.isAutoCustomerPricelistEnabled());
            }
            /**
             * Lines whose price must never be recomputed from a pricelist. Core already skips
             * lines flagged `price_manually_set` / `price_automatically_set` (manual prices,
             * refund lines, loyalty rewards); this also covers such lines created by
             * third-party code without the flags.
             */
            _ppcSnapshotGuardedLines() {
                const guarded = [];
                for (const line of this.get_orderlines() || []) {
                    if (line.price_manually_set || line.price_automatically_set) {
                        continue;
                    }
                    if (line.refunded_orderline_id || line.is_reward_line) {
                        guarded.push([line, line.price]);
                    }
                }
                return guarded;
            }
            _ppcRestoreGuardedLines(guarded) {
                for (const [line, price] of guarded) {
                    if (line.price !== price) {
                        line.price = price;
                    }
                }
            }
            _ppcApplyPricelist(pricelist, source) {
                this._ppcSource = source;
                try {
                    this.set_pricelist(pricelist);
                } finally {
                    this._ppcSource = null;
                }
            }
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
                        pricelist && defaultPricelist && pricelist.id === defaultPricelist.id ? 'default' : 'manual';
                }
                return result;
            }
            /**
             * Called by core (customer list, payment screen, partner barcode, refund, eWallet)
             * right after `set_partner`. The fiscal position logic of core is kept; only the
             * pricelist it picks is replaced by our resolution, so prices are recomputed once.
             */
            updatePricelist(newPartner) {
                if (!this._ppcEnabled()) {
                    return super.updatePricelist(...arguments);
                }
                if (this.getHasRefundLines()) {
                    // Refunds keep the pricelist and fiscal position of the refunded order
                    // (see TicketScreen patch); refund line prices are fixed anyway.
                    return;
                }
                const { pricelist, source } = this.pos.resolveCustomerPricelist(newPartner);
                this._ppcForcedPricelist = pricelist;
                this._ppcSource = source;
                try {
                    return super.updatePricelist(...arguments);
                } finally {
                    this._ppcForcedPricelist = null;
                    this._ppcSource = null;
                }
            }
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
                    this._ppcApplyPricelist(pricelist, 'refund');
                } else {
                    // not loaded here: backend sets the original pricelist on sync
                    this.pricelist_source = 'refund';
                }
            }
            getPricelistSourceLabel() {
                const labels = {
                    default: _t('POS Default'),
                    customer: _t('Customer Pricelist'),
                    manual: _t('Manually Selected'),
                    refund: _t('Refunded Order'),
                };
                return labels[this.pricelist_source] || '';
            }
            init_from_JSON(json) {
                super.init_from_JSON(...arguments);
                this.pricelist_source = json.pricelist_source || false;
            }
            export_as_JSON() {
                const json = super.export_as_JSON(...arguments);
                if (this._ppcEnabled()) {
                    json.pricelist_source = this.pricelist_source || false;
                }
                return json;
            }
            export_for_printing() {
                const receipt = super.export_for_printing(...arguments);
                if (this._ppcEnabled() && this.pos.config.receipt_show_pricelist && this.pricelist) {
                    receipt.ppc_pricelist_name = this.pricelist.display_name || this.pricelist.name;
                }
                return receipt;
            }
        };
    Registries.Model.extend(Order, PPCOrder);

    return { PPCPosGlobalState, PPCOrder };
});
