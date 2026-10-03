import ChangeBadge from "@/components/Change";
import CountUp from "@/components/CountUp";
import LineChart, { type Series } from "@/components/LineChart";
import { chainColor } from "@/lib/chains";
import { int, longDate, money } from "@/lib/format";
import { basketSize, chainSummary, forecasts, indexSeries, recentChanges, totals } from "@/lib/queries";

export const dynamic = "force-dynamic";

const shekel = (v: number) => `₪${Math.round(v).toLocaleString("he-IL")}`;

export default async function Overview() {
  const [summary, index, fc, t, ups, basket] = await Promise.all([
    chainSummary(),
    indexSeries(),
    forecasts(),
    totals(),
    recentChanges("increase", 6),
    basketSize(),
  ]);

  const ranked = summary
    .filter((s) => s.basket_cost != null)
    .map((s) => ({ ...s, basket_cost: Number(s.basket_cost), items_on_promo: Number(s.items_on_promo) }))
    .sort((a, b) => a.basket_cost - b.basket_cost);
  const cheapest = ranked[0];
  const priciest = ranked[ranked.length - 1];
  const above = (cost: number) => (cheapest ? Math.round((100 * (cost - cheapest.basket_cost)) / cheapest.basket_cost) : 0);
  const gap = cheapest && priciest && cheapest !== priciest ? above(priciest.basket_cost) : null;
  const promoTotal = ranked.reduce((n, s) => n + (s.items_on_promo || 0), 0);
  const maxPromo = Math.max(...ranked.map((s) => s.items_on_promo || 0), 1);

  const byChain = new Map<string, Series>();
  for (const p of index) {
    if (!byChain.has(p.chain_key))
      byChain.set(p.chain_key, { id: p.chain_key, label: p.chain_name_he, color: chainColor(p.chain_key), points: [] });
    byChain.get(p.chain_key)!.points.push({ x: p.day, y: p.price_index });
  }
  const indexLines = [...byChain.values()];

  const fcKey = cheapest?.chain_key;
  const fcPoints = fc.filter((f) => f.chain_key === fcKey);
  const fcHistory = fcKey ? byChain.get(fcKey) : undefined;
  const fcSeries: Series[] =
    fcHistory && fcPoints.length
      ? [
          { ...fcHistory, points: fcHistory.points.slice(-45) },
          {
            id: "fc",
            label: "תחזית",
            color: chainColor(fcKey!),
            dashed: true,
            points: [fcHistory.points[fcHistory.points.length - 1], ...fcPoints.map((f) => ({ x: f.target_date, y: f.yhat }))],
            band: fcPoints.map((f) => ({ x: f.target_date, lo: f.yhat_lower, hi: f.yhat_upper })),
          },
        ]
      : [];

  if (!cheapest) {
    return (
      <section className="panel">
        <h1 className="hero-title">עדיין אין נתונים</h1>
        <p className="hero-sub">הריצו את האיסוף היומי, והסל הראשון יופיע כאן.</p>
      </section>
    );
  }

  return (
    <>
      {/* ------------------------------------------------------------ hero -- */}
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-text">
          <p className="status">
            <span className="live" aria-hidden />
            עודכן {longDate(t?.newest)}
          </p>
          <h1 id="hero-title" className="hero-title">
            הסל הכי זול: <span className="grad">{cheapest.chain_name_he}</span>
          </h1>
          <p className="hero-sub">
            אותם {int(basket?.items)} מוצרים עולים {shekel(cheapest.basket_cost)} ב{cheapest.chain_name_he}
            {gap != null && ` ו-${shekel(priciest.basket_cost)} ב${priciest.chain_name_he}`}.
          </p>
        </div>
        <div className="hero-actions">
          <a className="btn btn-grad" href="/search">חיפוש מוצר</a>
          <a className="btn btn-ghost" href="/stores">השוואת סניפים</a>
        </div>
      </section>

      {/* ------------------------------------------------- ranking + winner -- */}
      <div className="grid-main">
        <section className="panel" style={{ ["--i" as string]: 0 }} aria-labelledby="rank-title">
          <header className="panel-head">
            <h2 id="rank-title">דירוג הרשתות</h2>
            {gap != null && <span className="chip chip-cyan">פער של {gap}%</span>}
          </header>

          <dl className="tiles">
            <div className="tile">
              <dt>מוצרים בסל</dt>
              <dd>{int(basket?.items)}</dd>
            </div>
            <div className="tile">
              <dt>סניפים במעקב</dt>
              <dd>{int(t?.stores)}</dd>
            </div>
            <div className="tile">
              <dt>מוצרים במבצע</dt>
              <dd>{int(promoTotal)}</dd>
            </div>
            <div className="tile">
              <dt>שינויי מחיר, 30 יום</dt>
              <dd>{int(t?.changes_30d)}</dd>
            </div>
          </dl>

          <ol className="track" style={{ ["--n" as string]: ranked.length }}>
            {ranked.map((s, i) => (
              <li
                key={s.chain_id}
                className={i === 0 ? "step step-win" : "step"}
                style={{ ["--d" as string]: `${300 + i * 260}ms`, ["--chain" as string]: chainColor(s.chain_key) }}
              >
                <span className="step-dot" aria-hidden>
                  {i + 1}
                </span>
                <span className="step-name">{s.chain_name_he}</span>
                <span className="step-cost">{shekel(s.basket_cost)}</span>
                <span className="step-diff">{i === 0 ? "הכי זול" : <bdi dir="ltr">+{above(s.basket_cost)}%</bdi>}</span>
              </li>
            ))}
          </ol>
        </section>

        <aside className="panel winner" style={{ ["--i" as string]: 1 }} aria-label="הרשת הזולה ביותר">
          <p className="winner-label">הכי זול היום</p>
          <p className="winner-name">{cheapest.chain_name_he}</p>
          <p className="winner-total">
            <CountUp value={cheapest.basket_cost} delayMs={500} decimals={0} />
          </p>
          <dl className="winner-facts">
            <div>
              <dt>חיסכון מול היקרה</dt>
              <dd>{gap != null ? shekel(priciest.basket_cost - cheapest.basket_cost) : "—"}</dd>
            </div>
            <div>
              <dt>סניפים</dt>
              <dd>{int(cheapest.tracked_stores)}</dd>
            </div>
            <div>
              <dt>מוצרים במבצע</dt>
              <dd>{int(cheapest.items_on_promo)}</dd>
            </div>
            <div>
              <dt>הנחה ממוצעת</dt>
              <dd>{cheapest.avg_promo_discount_pct != null ? `${cheapest.avg_promo_discount_pct}%` : "—"}</dd>
            </div>
          </dl>
          <a className="btn btn-grad btn-block" href="/stores">
            הסניפים הזולים
          </a>
        </aside>
      </div>

      {/* ------------------------------------------------- changes + promos -- */}
      <div className="grid-two">
        <section className="panel" style={{ ["--i" as string]: 2 }} aria-labelledby="ups-title">
          <header className="panel-head">
            <h2 id="ups-title">מה התייקר</h2>
            <a className="chip" href="/changes">
              כל השינויים
            </a>
          </header>
          {ups.length ? (
            <ul className="rows">
              {ups.map((c, i) => (
                <li key={i} className="row">
                  <span className="row-dot" style={{ background: chainColor(c.chain_key) }} aria-hidden />
                  <span className="row-main">
                    <a href={`/product/${encodeURIComponent(c.product_key)}`}>{c.product_name}</a>
                    <small>{c.chain_name_he}</small>
                  </span>
                  <span className="row-price">{money(c.new_price)}</span>
                  <ChangeBadge value={c.pct_change} />
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty">
              <span className="empty-icon" aria-hidden>
                ↗
              </span>
              <p>ההתייקרויות הראשונות יופיעו כאן אחרי האיסוף של מחר בבוקר.</p>
            </div>
          )}
        </section>

        <section className="panel" style={{ ["--i" as string]: 3 }} aria-labelledby="promo-title">
          <header className="panel-head">
            <h2 id="promo-title">מבצעים לפי רשת</h2>
          </header>
          <ul className="rows">
            {[...ranked]
              .sort((a, b) => b.items_on_promo - a.items_on_promo)
              .map((s, i) => (
                <li key={s.chain_id} className="row row-bar">
                  <span className="row-dot" style={{ background: chainColor(s.chain_key) }} aria-hidden />
                  <span className="row-main">
                    {s.chain_name_he}
                    <span className="meter" aria-hidden>
                      <span
                        style={{
                          width: `${(100 * (s.items_on_promo || 0)) / maxPromo}%`,
                          background: chainColor(s.chain_key),
                          ["--d" as string]: `${600 + i * 120}ms`,
                        }}
                      />
                    </span>
                  </span>
                  <span className="row-price">{int(s.items_on_promo)}</span>
                  <span className="chip chip-small">
                    {s.avg_promo_discount_pct != null ? `${Math.round(Number(s.avg_promo_discount_pct))}% הנחה` : "—"}
                  </span>
                </li>
              ))}
          </ul>
          <p className="panel-note">מספר המוצרים במבצע פתוח לכולם, וההנחה הממוצעת.</p>
        </section>
      </div>

      {/* ------------------------------------------------------------ index -- */}
      <section className="panel" style={{ ["--i" as string]: 4 }} aria-labelledby="idx-title">
        <header className="panel-head">
          <h2 id="idx-title">מדד מחירי הסל</h2>
          <span className="chip">100 = היום הראשון</span>
        </header>
        <LineChart
          series={indexLines}
          yLabel="מדד מחירים"
          valueFormat="index"
          emptyText="הגרף מתחיל אחרי יומיים של איסוף. מחר בבוקר תופיע כאן הנקודה השנייה."
        />
      </section>

      {fcSeries.length > 0 && (
        <section className="panel" style={{ ["--i" as string]: 5 }} aria-labelledby="fc-title">
          <header className="panel-head">
            <h2 id="fc-title">תחזית ל-14 יום: {cheapest.chain_name_he}</h2>
          </header>
          <LineChart series={fcSeries} yLabel="תחזית מדד" valueFormat="index" height={260} />
        </section>
      )}
    </>
  );
}
