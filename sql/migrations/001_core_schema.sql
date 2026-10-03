-- 001 — core schema
-- ingest : what we downloaded and what happened to it (idempotency + observability)
-- core   : cleaned, conformed entities; price history kept as SCD Type 2
-- marts  : built by dbt on top of core (see /dbt)

CREATE SCHEMA IF NOT EXISTS ingest;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS analytics;

-- ------------------------------------------------------------------ ingest --
CREATE TABLE IF NOT EXISTS ingest.file_log (
    file_name      text PRIMARY KEY,
    chain_id       text        NOT NULL,
    file_type      text        NOT NULL,
    store_id       integer,
    published_at   timestamp,
    sha256         text,
    size_bytes     bigint,
    row_count      integer,
    status         text        NOT NULL CHECK (status IN ('loaded', 'skipped', 'failed')),
    error          text,
    duration_ms    integer,
    processed_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS file_log_chain_type_idx ON ingest.file_log (chain_id, file_type, published_at DESC);

CREATE TABLE IF NOT EXISTS ingest.run_log (
    run_id         bigserial PRIMARY KEY,
    started_at     timestamptz NOT NULL DEFAULT now(),
    finished_at    timestamptz,
    status         text        NOT NULL DEFAULT 'running',
    files_loaded   integer     DEFAULT 0,
    files_failed   integer     DEFAULT 0,
    rows_loaded    bigint      DEFAULT 0,
    notes          text
);

-- -------------------------------------------------------------------- core --
CREATE TABLE IF NOT EXISTS core.chains (
    chain_id   text PRIMARY KEY,
    chain_key  text UNIQUE NOT NULL,
    name_he    text NOT NULL,
    name_en    text NOT NULL
);

CREATE TABLE IF NOT EXISTS core.stores (
    chain_id       text    NOT NULL REFERENCES core.chains (chain_id),
    store_id       integer NOT NULL,
    store_name     text,
    subchain_id    text,
    subchain_name  text,
    address        text,
    city           text,
    zip_code       text,
    store_type     text,
    is_tracked     boolean NOT NULL DEFAULT false,
    first_seen_at  timestamptz NOT NULL DEFAULT now(),
    last_seen_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (chain_id, store_id)
);

-- A product is identified by its barcode when it has one (shared across chains),
-- otherwise by a chain-scoped internal code: '<chain_id>:<code>'.
CREATE TABLE IF NOT EXISTS core.products (
    product_key          text PRIMARY KEY,
    item_code            text    NOT NULL,
    is_barcode           boolean NOT NULL,
    owner_chain_id       text,                -- only for internal codes
    item_name            text,
    manufacturer_name    text,
    manufacture_country  text,
    unit_qty             text,
    quantity             numeric(12, 3),
    unit_of_measure      text,
    is_weighted          boolean,
    first_seen_at        timestamptz NOT NULL DEFAULT now(),
    last_seen_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS products_name_idx ON core.products (item_name);

-- SCD Type 2: one row per (store, product, price period).
-- valid_to IS NULL  → the price currently on the shelf.
-- A full price file closes rows for products no longer listed (delisting).
CREATE TABLE IF NOT EXISTS core.price_history (
    chain_id               text          NOT NULL,
    store_id               integer       NOT NULL,
    product_key            text          NOT NULL REFERENCES core.products (product_key),
    item_price             numeric(10, 2) NOT NULL CHECK (item_price > 0),
    unit_of_measure_price  numeric(12, 4),
    chain_item_name        text,
    allow_discount         boolean,
    item_status            smallint,
    price_update_date      timestamp,
    valid_from             timestamp     NOT NULL,
    valid_to               timestamp,
    source_file            text          NOT NULL,
    PRIMARY KEY (chain_id, store_id, product_key, valid_from),
    FOREIGN KEY (chain_id, store_id) REFERENCES core.stores (chain_id, store_id),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE UNIQUE INDEX IF NOT EXISTS price_history_current_uq
    ON core.price_history (chain_id, store_id, product_key) WHERE valid_to IS NULL;
CREATE INDEX IF NOT EXISTS price_history_product_idx
    ON core.price_history (product_key, valid_from);

CREATE TABLE IF NOT EXISTS core.promotions (
    chain_id             text    NOT NULL,
    store_id             integer NOT NULL,
    promotion_id         text    NOT NULL,
    description          text,
    start_at             timestamp,
    end_at               timestamp,
    update_date          timestamp,
    reward_type          smallint,
    min_qty              numeric(10, 3),
    max_qty              numeric(10, 3),
    discounted_price     numeric(10, 2),
    discount_rate        numeric(10, 2),
    min_purchase_amount  numeric(10, 2),
    is_club_only         boolean NOT NULL DEFAULT false,
    item_count           integer NOT NULL DEFAULT 0,
    first_seen_at        timestamptz NOT NULL DEFAULT now(),
    last_seen_at         timestamptz NOT NULL DEFAULT now(),
    source_file          text,
    PRIMARY KEY (chain_id, store_id, promotion_id),
    FOREIGN KEY (chain_id, store_id) REFERENCES core.stores (chain_id, store_id)
);

CREATE TABLE IF NOT EXISTS core.promotion_items (
    chain_id      text    NOT NULL,
    store_id      integer NOT NULL,
    promotion_id  text    NOT NULL,
    product_key   text    NOT NULL,
    PRIMARY KEY (chain_id, store_id, promotion_id, product_key),
    FOREIGN KEY (chain_id, store_id, promotion_id)
        REFERENCES core.promotions (chain_id, store_id, promotion_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS promotion_items_product_idx ON core.promotion_items (product_key);

