import ChangeBadge from "@/components/Change";
import LineChart from "@/components/LineChart";
import { chainColor } from "@/lib/chains";
import { money, shortDate } from "@/lib/format";
import { anomalies, dailyChanges, recentChanges } from "@/lib/queries";

export const dynamic = "force-dynamic";

export default async function Changes({ searchParams }: { searchParams: Promise<{ dir?: string }> }) {
  const { dir } = await searchParams;
  const direction = dir === "increase" || dir === "decrease" ? dir : null;
  const [rows, daily, anom] = await Promise.all([recentChanges(direction, 100), dailyChanges(), anomalies()]);

  return (
    <>
      <h1 className="display page-title">מה השתנה על המדף</h1>
      <p className="lede">כל שינוי במחיר המדף בסניפים שבמעקב, ב-30 הימים האחרונים.</p>

      <section className="block flush">
        <h2>התייקרויות מול הוזלות ליום</h2>
        <p className="section-sub">מספר שינויי המחיר בכל הרשתות</p>
        <LineChart
          height={220}
          valueFormat="int"
          emptyText="הגרף יופיע אחרי יומיים של איסוף, כשיהיה מה להשוות."
          series={[
            { id: "up", label: "התייקרויות", color: "var(--up)", points: daily.map((d) => ({ x: d.change_date, y: d.n_increases })) },
            { id: "down", label: "הוזלות", color: "var(--down)", points: daily.map((d) => ({ x: d.change_date, y: d.n_decreases })) },
          ]}
        />
      </section>

      <form className="search" action="/changes">
        <select name="dir" defaultValue={direction ?? ""} aria-label="כיוון">
          <option value="">הכול</option>
          <option value="increase">התייקרויות</option>
          <option value="decrease">הוזלות</option>
        </select>
        <button type="submit">סינון</button>
      </form>

      <section className="block flush">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>תאריך</th>
                <th>מוצר</th>
                <th>סניף</th>
                <th className="num">לפני</th>
                <th className="num">אחרי</th>
                <th className="num">שינוי</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c, i) => (
                <tr key={i}>
                  <td>{shortDate(c.change_date)}</td>
                  <td>
                    <a href={`/product/${encodeURIComponent(c.product_key)}`}>{c.product_name}</a>
                  </td>
                  <td>
                    <span className="chain-dot" style={{ background: chainColor(c.chain_key) }} />
                    {c.store_name}
                  </td>
                  <td className="num">{money(c.previous_price)}</td>
                  <td className="num">{money(c.new_price)}</td>
                  <td className="num">
                    <ChangeBadge value={c.pct_change} />
                  </td>
                </tr>
              ))}
              {!rows.length && (
                <tr>
                  <td colSpan={6} className="empty-cell">
                    עדיין לא נרשמו שינויי מחיר. השינויים הראשונים יופיעו אחרי איסוף הנתונים של מחר בבוקר.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="block flush">
        <h2>מחירים חריגים</h2>
        <p className="section-sub">
          סניף שמתמחר ברקוד רחוק מאוד משאר הסניפים של אותה רשת (ציון z חסין, MAD). יכול להיות טעות בקובץ של הרשת — או
          שינוי מחיר מקומי.
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>מוצר</th>
                <th>סניף</th>
                <th className="num">מחיר</th>
                <th className="num">חציון</th>
                <th className="num">z</th>
              </tr>
            </thead>
            <tbody>
              {anom.map((a, i) => (
                <tr key={i}>
                  <td>
                    <a href={`/product/${encodeURIComponent(a.product_key)}`}>{a.product_name}</a>
                  </td>
                  <td>{a.store_name}</td>
                  <td className="num">{money(a.item_price)}</td>
                  <td className="num">{money(a.peer_median)}</td>
                  <td className="num">{a.robust_z.toFixed(1)}</td>
                </tr>
              ))}
              {!anom.length && (
                <tr>
                  <td colSpan={5} className="empty-cell">היום לא נמצאו מחירים חריגים.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
