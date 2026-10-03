-- 002 — tables written by the Python analytics jobs (src/pricetracker/analytics)

CREATE TABLE IF NOT EXISTS analytics.price_anomalies (
    detected_on     date          NOT NULL,
    chain_id        text          NOT NULL,
    store_id        integer       NOT NULL,
    product_key     text          NOT NULL,
    item_price      numeric(10, 2) NOT NULL,
    peer_median     numeric(10, 2) NOT NULL,
    peer_count      integer       NOT NULL,
    robust_z        numeric(10, 2) NOT NULL,
    kind            text          NOT NULL CHECK (kind IN ('overpriced', 'underpriced', 'jump')),
    PRIMARY KEY (detected_on, chain_id, store_id, product_key, kind)
);

CREATE TABLE IF NOT EXISTS analytics.index_forecast (
    chain_id        text          NOT NULL,
    target_date     date          NOT NULL,
    horizon_days    integer       NOT NULL,
    yhat            numeric(10, 3) NOT NULL,
    yhat_lower      numeric(10, 3) NOT NULL,
    yhat_upper      numeric(10, 3) NOT NULL,
    model           text          NOT NULL,
    created_at      timestamptz   NOT NULL DEFAULT now(),
    PRIMARY KEY (chain_id, target_date, model)
);

CREATE TABLE IF NOT EXISTS analytics.model_backtest (
    chain_id        text          NOT NULL,
    model           text          NOT NULL,
    mae             numeric(10, 4) NOT NULL,
    mape            numeric(10, 4),
    n_points        integer       NOT NULL,
    created_at      timestamptz   NOT NULL DEFAULT now(),
    PRIMARY KEY (chain_id, model)
);
