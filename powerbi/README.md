# Power BI report

The dbt marts form a **star schema** that Power BI imports directly.

```
                 dim_date
                    │ date_day
 dim_chain ──┬── fct_price_changes ──┬── dim_product
             │                       │
             ├── fct_current_price ──┤
             │        │ store_key    │
             │     dim_store         │
             └── mart_basket_index_daily (chain × day)
```

## 1. Connect

1. Power BI Desktop → **Get data → PostgreSQL database**
2. **Server:** the host from your Neon connection string, e.g.
   `ep-cool-name-123456.eu-central-1.aws.neon.tech` (Neon → Connect; use the host *without* `-pooler` here)
   **Database:** `neondb`
3. Data connectivity mode: **Import** (the marts are small and refresh daily).
4. Credentials: **Database** → user `web_reader` and its password
   (read-only role from `sql/migrations/003_web_access.sql`).
   If you get *"Endpoint ID is not specified"*, the driver doesn't send SNI: enter the password as
   `endpoint=<endpoint-id>;<password>` where `<endpoint-id>` is the first part of the host (`ep-cool-name-123456`).
5. Select these tables from the `marts` schema:

| Table | Grain | Role |
|---|---|---|
| `dim_chain` | chain | dimension |
| `dim_store` | branch | dimension |
| `dim_product` | product (with category) | dimension |
| `dim_date` | day | date table |
| `fct_current_price` | branch × product, today | fact |
| `fct_price_changes` | one price change | fact |
| `mart_basket_index_daily` | chain × day | aggregate fact |
| `mart_store_basket` | branch | aggregate |

## 2. Model

**Modeling → Manage relationships** (all single-direction, many-to-one):

| From (many) | To (one) |
|---|---|
| `fct_current_price[store_key]` | `dim_store[store_key]` |
| `fct_current_price[product_key]` | `dim_product[product_key]` |
| `fct_current_price[chain_id]` | `dim_chain[chain_id]` |
| `fct_price_changes[store_key]` | `dim_store[store_key]` |
| `fct_price_changes[product_key]` | `dim_product[product_key]` |
| `fct_price_changes[chain_id]` | `dim_chain[chain_id]` |
| `fct_price_changes[change_date]` | `dim_date[date_day]` |
| `mart_basket_index_daily[chain_id]` | `dim_chain[chain_id]` |
| `mart_basket_index_daily[day]` | `dim_date[date_day]` |

Then: select `dim_date` → **Mark as date table** (`date_day`).
Do **not** relate `dim_store` to `dim_chain`: the facts already carry `chain_id`, and a
second path would make the model ambiguous. Chain filters flow through the facts.

## 3. Measures

Create a `_Measures` table and paste everything from [`measures.dax`](measures.dax).

## 4. Suggested pages

1. **Overview** — cards: Basket Cost (cheapest chain), Basket Gap %, Price Changes (Last 30d);
   clustered bar: Basket Cost by chain; line: Price Index by day, legend = chain.
2. **Product explorer** — slicer on `dim_product[category_he]` and product name;
   table: chain, store, effective price, Premium vs Best %.
3. **Price changes** — column chart Price Increases vs Decreases by week;
   matrix: category × chain with Avg Increase %.
4. **Branches** — table from `mart_store_basket`, slicer on city, conditional formatting on basket cost.

Match the web dashboard: **View → Themes → Browse for themes →** [`theme.json`](theme.json)
(dark navy background, chain colours in the same order as the site).
Then fix each chain's colour so it never depends on sort order (**Format → Data colors**):
Shufersal `#60a5fa`, Rami Levy `#fb923c`, Osher Ad `#34d399`, Yohananof `#facc15`, Tiv Taam `#f472b6`.

## 5. Refresh

The pipeline updates the database every morning. In Power BI Desktop click **Refresh**;
in the Power BI Service set a scheduled refresh after 08:00.
