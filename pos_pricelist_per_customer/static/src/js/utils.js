/** @odoo-module */

/**
 * Shared, RPC-free helpers. Everything needed is already in memory: partners carry
 * `pos_assigned_pricelist_id`, the config carries its available pricelists.
 */
export function isAutoCustomerPricelistEnabled(config) {
    return Boolean(config && config.auto_customer_pricelist && config.use_pricelist);
}

export function getAvailablePricelist(config, pricelistId) {
    if (!config || !pricelistId) {
        return undefined;
    }
    const available = config.available_pricelist_ids || [];
    return (
        available.find((pricelist) => pricelist.id === pricelistId) ||
        (config.pricelist_id?.id === pricelistId ? config.pricelist_id : undefined)
    );
}

/**
 * @param {Object} config pos.config record
 * @param {Object|null} partner res.partner record
 * @returns {{pricelist: Object, source: 'customer'|'default'}}
 */
export function resolveCustomerPricelist(config, partner) {
    const raw = partner && partner.pos_assigned_pricelist_id;
    // many2one may come as a record or as a raw id when the pricelist is not loaded
    const pricelistId = raw && typeof raw === "object" ? raw.id : raw;
    if (pricelistId) {
        // inactive / foreign-company pricelists are filtered server side,
        // pricelists not available in this POS are ignored here.
        const pricelist = getAvailablePricelist(config, pricelistId);
        if (pricelist) {
            return { pricelist, source: "customer" };
        }
    }
    return { pricelist: config.pricelist_id, source: "default" };
}
