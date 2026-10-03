import { notFound } from "next/navigation";
import BarList from "@/components/BarList";
import LineChart, { type Series } from "@/components/LineChart";
import { chainColor } from "@/lib/chains";
import { money } from "@/lib/format";
import { product, productChainPrices, productHistory, productStorePrices } from "@/lib/queries";

export const dynamic = "force-dynamic";

export default async function ProductPage({ params }: { params: Promise<{ key: string }> }) {
  const { key: raw } = await params;
  const key = decodeURIComponent(raw);
  const p = await product(key);
  if (!p) notFound();
  const [chains, stores, history] = await Promise.all([
    productChainPrices(key),
    productStorePrices(key),
    productHistory(key),
  ]);

  const lines = new Map<string, Series>();
  for (const h of history) {
    if (!lines.has(h.chain_key))
      lines.set(h.chain_key, { id: h.chain_key, label: h.chain_name_he, color: chainColor(h.chain_key), points: [] });
    lines.get(h.chain_key)!.points.push({ x: h.day, y: h.price });
  }
  const best = chains[0];
  const worst = chains[chains.length - 1];

  return (
    <>
      <p className="muted" style={{ margin: 0 }}>
        {p.category_he} · ברקוד {p.item_code}
      </p>
      <h1 className="display page-title">{p.product_name}</h1>
      <p className="lede">
        {p.manufacturer_name ? `${p.manufacturer_name}. ` : ""}
        {best && worst && chains.length > 1
          ? `הכי זול ב${best.chain_name_he} (${money(best.min_price)}), ויקר ב-${worst.pct_above_best}% ב${worst.chain_name_he}.`
          : "המוצר נמכר כרגע ברשת אחת מבין הרשתות במעקב."}
      </p>

      <div className="two">
        <section className="block flush">
          <h2>המחיר הנמוך ביותר לפי רשת</h2>
          <p className="section-sub">מחיר אפקטיבי היום (מדף או מבצע פתוח לכולם, ליחידה)</p>
          <BarList
            rows={chains.map((c) => ({
              id: c.chain_key,
              label: c.chain_name_he,
              value: c.min_price,
              color: chainColor(c.chain_key),
              highlight: c.is_cheapest,
              note: c.any_promo ? "יש מבצע באחד הסניפים" : undefined,
            }))}
            format={money}
          />
        </section>
        <section className="block flush">
          <h2>היסטוריית מחיר (90 יום)</h2>
          <p className="section-sub">מחיר המדף הנמוך ביותר ברשת, לפי יום</p>
          <LineChart series={[...lines.values()]} valueFormat="ils" height={240} />
        </section>
      </div>

      <section className="block flush">
        <h2>כל הסניפים</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>סניף</th>
                <th>עיר</th>
                <th className="num">מחיר מדף</th>
                <th className="num">מחיר אפקטיבי</th>
                <th>מבצע</th>
              </tr>
            </thead>
            <tbody>
              {stores.map((s, i) => (
                <tr key={i}>
                  <td>
                    <span className="chain-dot" style={{ background: chainColor(s.chain_key) }} />
                    {s.store_name}
                  </td>
                  <td>{s.city ?? "—"}</td>
                  <td className="num">{money(s.regular_price)}</td>
                  <td className="num">
                    <b>{money(s.effective_price)}</b>
                  </td>
                  <td>
                    {s.promo_description && <span className="pill promo">{s.promo_description}</span>}
                    {s.club_unit_price != null && (
                      <span className="pill" style={{ marginInlineStart: 6 }}>
                        מועדון: {money(s.club_unit_price)}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
