-- Products with a category inferred from Hebrew keywords (seeds/category_keywords.csv).
with matches as (
    select
        p.product_key,
        k.category_en,
        k.category_he,
        row_number() over (partition by p.product_key order by k.priority, length(k.keyword) desc) as rn
    from {{ ref('stg_products') }} p
    join {{ ref('category_keywords') }} k
      on position(k.keyword in p.product_name) > 0
)

select
    p.product_key,
    p.item_code,
    p.is_barcode,
    p.product_name,
    p.manufacturer_name,
    p.manufacture_country,
    p.quantity,
    p.unit_qty,
    p.unit_of_measure,
    p.is_weighted,
    coalesce(m.category_en, 'Other')  as category_en,
    coalesce(m.category_he, 'אחר')    as category_he,
    b.product_key is not null          as is_basket_product,
    p.first_seen_at
from {{ ref('stg_products') }} p
left join matches m on m.product_key = p.product_key and m.rn = 1
left join {{ ref('int_basket_products') }} b on b.product_key = p.product_key
