-- 004 — since 2026 the chains publish the reward on each promotion item
-- (Groups/PromotionItems/PromotionItem), not on the promotion itself.

ALTER TABLE core.promotions
    ADD COLUMN IF NOT EXISTS is_coupon boolean NOT NULL DEFAULT false;

ALTER TABLE core.promotion_items
    ADD COLUMN IF NOT EXISTS reward_type      smallint,
    ADD COLUMN IF NOT EXISTS min_qty          numeric(10, 3),
    ADD COLUMN IF NOT EXISTS discounted_price numeric(10, 2),
    ADD COLUMN IF NOT EXISTS price_per_unit   numeric(12, 4),
    ADD COLUMN IF NOT EXISTS discount_rate    numeric(10, 2);
