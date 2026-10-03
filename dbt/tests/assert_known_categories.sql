-- keyword-priority regression checks for the category rules
with cases (name, expected) as (
    values ('שוקולד חלב 100 גרם', 'Snacks & Sweets'),
           ('חלב טרי 3% קרטון 1 ליטר', 'Dairy & Eggs'),
           ('חזה עוף במשקל', 'Meat & Fish'),
           ('קפה נמס 200 גרם', 'Coffee & Tea')
),
matched as (
    select c.name, c.expected, k.category_en,
           row_number() over (partition by c.name order by k.priority, length(k.keyword) desc) as rn
    from cases c join {{ ref('category_keywords') }} k on position(k.keyword in c.name) > 0
)
select * from matched where rn = 1 and category_en <> expected
