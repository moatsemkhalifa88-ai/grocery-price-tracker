import { money } from "@/lib/format";
import { popularProducts, searchProducts, type ProductHit } from "@/lib/queries";

export const dynamic = "force-dynamic";

export default async function Search({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams;
  const term = q.trim().slice(0, 60);
  const hits: ProductHit[] = term ? await searchProducts(term) : await popularProducts();

  return (
    <>
      <h1 className="display page-title">באיזו רשת זה הכי זול?</h1>
      <p className="lede">חפשו מוצר לפי שם או ברקוד, ותראו את המחיר הנמוך ביותר בכל רשת, כולל מבצעים.</p>
      <form className="search" action="/search">
        <input name="q" defaultValue={term} placeholder="למשל: חלב, קפה, 7290000042640" aria-label="חיפוש מוצר" />
        <button type="submit">חיפוש</button>
      </form>
      <h2 className="list-title">
        {term ? `${hits.length} תוצאות עבור ״${term}״` : "הפערים הגדולים ביותר בין הרשתות"}
      </h2>
      <div className="shelf">
        {hits.map((p) => (
          <a key={p.product_key} href={`/product/${encodeURIComponent(p.product_key)}`} className="shelf-tag">
            <span className="st-name">{p.product_name}</span>
            <span className="st-meta">{p.manufacturer_name ?? p.category_he}</span>
            <span className="st-price">{money(p.best_price)}</span>
            <span className="st-where">הכי זול ב{p.cheapest_chain}, מתוך {p.n_chains} רשתות</span>
          </a>
        ))}
      </div>
      {term && !hits.length && (
        <p className="empty">לא מצאנו מוצר בשם הזה. נסו מילה קצרה יותר, למשל ״חלב״ במקום ״חלב טרי 3%״.</p>
      )}
    </>
  );
}
