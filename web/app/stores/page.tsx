import { chainColor } from "@/lib/chains";
import { money } from "@/lib/format";
import { chainsForFilter, storeBaskets } from "@/lib/queries";

export const dynamic = "force-dynamic";

export default async function Stores({ searchParams }: { searchParams: Promise<{ chain?: string }> }) {
  const { chain = "" } = await searchParams;
  const [rows, chains] = await Promise.all([storeBaskets(chain || null), chainsForFilter()]);

  return (
    <>
      <h1 className="display page-title">איזה סניף הכי משתלם?</h1>
      <p className="lede">
        עלות הסל המשותף בכל סניף, לפי המחירים של היום. הדירוג מתחשב במחיר הממוצע לפריט, כך שסניף שחסרים בו מוצרים לא
        ייראה זול רק בגלל זה.
      </p>
      <form className="search" action="/stores">
        <select name="chain" defaultValue={chain} aria-label="רשת">
          <option value="">כל הרשתות</option>
          {chains.map((c) => (
            <option key={c.chain_key} value={c.chain_key}>
              {c.chain_name_he}
            </option>
          ))}
        </select>
        <button type="submit">הצגה</button>
      </form>
      <section className="block flush">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>סניף</th>
                <th>רשת</th>
                <th className="num">עלות סל</th>
                <th className="num">כיסוי</th>
                <th className="num">פריטים במבצע</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.store_key}>
                  <td>
                    <span className={`rank ${i === 0 ? "first" : ""}`}>{i + 1}</span>
                  </td>
                  <td>
                    {r.store_name}
                  </td>
                  <td>
                    <span className="chain-dot" style={{ background: chainColor(r.chain_key) }} />
                    {r.chain_name_he}
                  </td>
                  <td className="num">{money(r.basket_cost)}</td>
                  <td className="num">
                    {r.basket_items_available}/{r.basket_items_total}
                  </td>
                  <td className="num">{r.items_on_promo}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
