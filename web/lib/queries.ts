import "server-only";
import { query } from "./db";

export type ChainSummary = {
  chain_id: string;
  chain_key: string;
  chain_name_he: string;
  tracked_stores: number;
  products_listed: number | null;
  index_date: string | null;
  price_index: number | null;
  basket_cost: number | null;
  basket_rank: number;
  increases_30d: number;
  decreases_30d: number;
  avg_change_pct_30d: number | null;
  items_on_promo: number;
  avg_promo_discount_pct: number | null;
};

export const chainSummary = () =>
  query<ChainSummary>(`select * from marts.mart_chain_summary order by basket_rank, chain_key`);

export type IndexPoint = { chain_key: string; chain_name_he: string; day: string; price_index: number; basket_cost: number | null };

export const indexSeries = () =>
  query<IndexPoint>(
    `select c.chain_key, c.chain_name_he, i.day::text as day, i.price_index, i.basket_cost
     from marts.mart_basket_index_daily i join marts.dim_chain c using (chain_id)
     where i.day > current_date - 120
     order by i.day`
  );

export type ForecastPoint = { chain_key: string; target_date: string; yhat: number; yhat_lower: number; yhat_upper: number };

export const forecasts = () =>
  query<ForecastPoint>(
    `select c.chain_key, f.target_date::text as target_date, f.yhat, f.yhat_lower, f.yhat_upper
     from analytics.index_forecast f join marts.dim_chain c using (chain_id)
     order by f.target_date`
  );

export type Backtest = { chain_key: string; model: string; mae: number; n_points: number };
export const backtests = () =>
  query<Backtest>(
    `select c.chain_key, b.model, b.mae, b.n_points
     from analytics.model_backtest b join marts.dim_chain c using (chain_id)`
  );

export type Totals = { stores: number; products: number; changes_30d: number; newest: string | null };
export const totals = async () =>
  (
    await query<Totals>(
      `select
         (select count(*) from marts.dim_store where is_tracked)              as stores,
         (select count(distinct product_key) from marts.fct_current_price)   as products,
         (select count(*) from marts.fct_price_changes where change_date > current_date - 30) as changes_30d,
         (select max(newest_file_at)::text from marts.mart_pipeline_health)  as newest`
    )
  )[0];

export type Change = {
  product_key: string;
  product_name: string;
  chain_key: string;
  chain_name_he: string;
  store_name: string;
  change_date: string;
  previous_price: number;
  new_price: number;
  pct_change: number;
};

export const recentChanges = (direction: "increase" | "decrease" | null, limit = 50) =>
  query<Change>(
    `select f.product_key, p.product_name, c.chain_key, c.chain_name_he, s.store_name,
            f.change_date::text as change_date, f.previous_price, f.new_price, f.pct_change
     from marts.fct_price_changes f
     join marts.dim_product p using (product_key)
     join marts.dim_store s using (store_key)
     join marts.dim_chain c on c.chain_id = f.chain_id
     where ($1::text is null or f.direction = $1)
       and f.change_date > current_date - 30
     order by f.change_date desc, abs(f.pct_change) desc
     limit $2`,
    [direction, limit]
  );

// Home page: one row per product+chain, everyday products first, and no
// extreme jumps (>100% is usually a clearance price ending, not a price rise;
// those are listed on /changes as anomalies instead).
export const homeIncreases = (limit = 6) =>
  query<Change>(
    `select * from (
       select distinct on (f.product_key, f.chain_id)
              f.product_key, p.product_name, c.chain_key, c.chain_name_he, s.store_name,
              f.change_date::text as change_date, f.previous_price, f.new_price, f.pct_change,
              p.is_basket_product
       from marts.fct_price_changes f
       join marts.dim_product p using (product_key)
       join marts.dim_store s using (store_key)
       join marts.dim_chain c on c.chain_id = f.chain_id
       where f.direction = 'increase'
         and f.change_date > current_date - 7
         and f.pct_change <= 100
       order by f.product_key, f.chain_id, f.change_date desc
     ) x
     order by is_basket_product desc, pct_change desc
     limit $1`,
    [limit]
  );

export type DailyChanges = { change_date: string; n_increases: number; n_decreases: number };
export const dailyChanges = () =>
  query<DailyChanges>(
    `select change_date::text as change_date, sum(n_increases)::int as n_increases, sum(n_decreases)::int as n_decreases
     from marts.mart_daily_changes where change_date > current_date - 60
     group by 1 order by 1`
  );

export type Anomaly = {
  product_key: string; product_name: string; chain_name_he: string; store_name: string;
  item_price: number; peer_median: number; robust_z: number; kind: string;
};
export const anomalies = () =>
  query<Anomaly>(
    `select a.product_key, p.product_name, c.chain_name_he, s.store_name,
            a.item_price, a.peer_median, a.robust_z, a.kind
     from analytics.price_anomalies a
     join marts.dim_product p using (product_key)
     join marts.dim_chain c using (chain_id)
     join marts.dim_store s on s.chain_id = a.chain_id and s.store_id = a.store_id
     where a.detected_on = (select max(detected_on) from analytics.price_anomalies)
       and a.kind <> 'jump'
     order by abs(a.robust_z) desc limit 20`
  );

export type ProductHit = {
  product_key: string; product_name: string; manufacturer_name: string | null; category_he: string;
  n_chains: number; best_price: number; cheapest_chain: string;
};
export const searchProducts = (q: string) =>
  query<ProductHit>(
    `select p.product_key, p.product_name, p.manufacturer_name, p.category_he,
            max(m.n_chains)::int as n_chains, min(m.min_price) as best_price,
            (array_agg(c.chain_name_he order by m.min_price))[1] as cheapest_chain
     from marts.dim_product p
     join marts.mart_product_chain_price m using (product_key)
     join marts.dim_chain c on c.chain_id = m.chain_id
     where p.product_name ilike '%' || $1 || '%' or p.item_code = $1
     group by 1, 2, 3, 4
     order by max(m.n_chains) desc, p.product_name
     limit 40`,
    [q]
  );

export const popularProducts = () =>
  query<ProductHit>(
    `select p.product_key, p.product_name, p.manufacturer_name, p.category_he,
            max(m.n_chains)::int as n_chains, min(m.min_price) as best_price,
            (array_agg(c.chain_name_he order by m.min_price))[1] as cheapest_chain
     from marts.dim_product p
     join marts.mart_product_chain_price m using (product_key)
     join marts.dim_chain c on c.chain_id = m.chain_id
     where p.is_basket_product
     group by 1, 2, 3, 4
     order by max(m.pct_above_best) desc nulls last
     limit 12`
  );

export type Product = {
  product_key: string; item_code: string; product_name: string; manufacturer_name: string | null;
  category_he: string; quantity: number | null; unit_qty: string | null;
};
export const product = async (key: string) =>
  (
    await query<Product>(
      `select product_key, item_code, product_name, manufacturer_name, category_he, quantity, unit_qty
       from marts.dim_product where product_key = $1`,
      [key]
    )
  )[0];

export type ChainPrice = {
  chain_key: string; chain_name_he: string; min_price: number; avg_price: number; n_stores: number;
  is_cheapest: boolean; pct_above_best: number; any_promo: boolean;
};
export const productChainPrices = (key: string) =>
  query<ChainPrice>(
    `select c.chain_key, c.chain_name_he, m.min_price, m.avg_price, m.n_stores, m.is_cheapest,
            m.pct_above_best, m.any_promo
     from marts.mart_product_chain_price m join marts.dim_chain c using (chain_id)
     where m.product_key = $1 order by m.min_price`,
    [key]
  );

export type StorePrice = {
  chain_key: string; chain_name_he: string; store_name: string; city: string | null;
  regular_price: number; effective_price: number; promo_description: string | null; club_unit_price: number | null;
};
export const productStorePrices = (key: string) =>
  query<StorePrice>(
    `select c.chain_key, c.chain_name_he, s.store_name, s.city, f.regular_price, f.effective_price,
            f.promo_description, f.club_unit_price
     from marts.fct_current_price f
     join marts.dim_store s using (store_key)
     join marts.dim_chain c on c.chain_id = f.chain_id
     where f.product_key = $1 order by f.effective_price, c.chain_key`,
    [key]
  );

export type HistoryPoint = { chain_key: string; chain_name_he: string; day: string; price: number };
// daily chain-minimum shelf price for one product, last 90 days
export const productHistory = (key: string) =>
  query<HistoryPoint>(
    `with days as (
       select generate_series(current_date - 89, current_date, interval '1 day')::date as day
     )
     select c.chain_key, c.chain_name_he, d.day::text as day, min(h.item_price) as price
     from days d
     join marts.fct_price_history h
       on h.product_key = $1 and h.valid_from < d.day + 1 and (h.valid_to is null or h.valid_to >= d.day + 1)
     join marts.dim_chain c using (chain_id)
     group by 1, 2, 3 order by 3`,
    [key]
  );

export type StoreBasket = {
  store_key: string; chain_key: string; chain_name_he: string; store_name: string; city: string | null;
  basket_items_available: number; basket_items_total: number; coverage_pct: number | null;
  basket_cost: number | null; items_on_promo: number; value_rank: number;
};
export const storeBaskets = (chainKey: string | null) =>
  query<StoreBasket>(
    `select b.store_key, c.chain_key, b.chain_name_he, b.store_name, b.city, b.basket_items_available,
            b.basket_items_total, b.coverage_pct, b.basket_cost, b.items_on_promo, b.value_rank
     from marts.mart_store_basket b join marts.dim_chain c using (chain_id)
     where ($1::text is null or c.chain_key = $1)
     order by b.value_rank`,
    [chainKey]
  );

export const cities = () =>
  query<{ city: string }>(
    `select distinct city from marts.dim_store where is_tracked and city is not null order by city`
  );

export type ReceiptRow = { chain_key: string; product_key: string; product_name: string; avg_price: number; rnk: number };
// The receipt lines: one well-stocked product per everyday category that EVERY
// chain sells, so all receipts list the same, recognisable basket.
export const receiptLines = (limit = 6) =>
  query<ReceiptRow>(
    `with n as (select count(*) as chains from marts.dim_chain where tracked_stores > 0),
     candidates as (
       select m.product_key, p.category_en, p.product_name, sum(m.n_stores) as stores
       from marts.mart_product_chain_price m
       join marts.dim_product p using (product_key)
       where p.is_basket_product and p.category_en <> 'Other'
         and m.n_chains = (select chains from n)
       group by 1, 2, 3
     ),
     per_category as (
       select *, row_number() over (partition by category_en order by stores desc, product_key) as rn
       from candidates
     ),
     picks as (
       select product_key,
              row_number() over (order by array_position(array['Dairy & Eggs','Bakery','Pantry','Beverages',
                'Snacks & Sweets','Coffee & Tea','Cleaning','Meat & Fish','Personal Care','Paper & Baby',
                'Deli & Salads','Fruit & Veg']::text[], category_en)) as rnk
       from per_category where rn = 1
     )
     select c.chain_key, k.product_key, p.product_name, m.avg_price, k.rnk
     from picks k
     join marts.mart_product_chain_price m using (product_key)
     join marts.dim_product p using (product_key)
     join marts.dim_chain c on c.chain_id = m.chain_id
     where k.rnk <= $1
     order by k.rnk`,
    [limit]
  );

export type BasketSize = { items: number };
export const basketSize = async () =>
  (await query<BasketSize>(`select coalesce(max(basket_items_total), 0)::int as items from marts.mart_store_basket`))[0];

export const chainsForFilter = () =>
  query<{ chain_key: string; chain_name_he: string }>(
    `select chain_key, chain_name_he from marts.dim_chain where tracked_stores > 0 order by chain_name_he`
  );
