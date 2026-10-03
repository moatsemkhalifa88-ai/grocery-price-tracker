import CountUp from "./CountUp";

export type ReceiptLine = { name: string; price: number };

type Props = {
  chainName: string;
  color: string;
  stores: number;
  lines: ReceiptLine[];
  moreCount: number;
  total: number;
  isCheapest: boolean;
  premiumPct: number | null;
  index: number;
};

// chains sometimes put tags like "*מבצע*" inside the product name itself
const cleanName = (n: string) => n.replace(/\*[^*]*\*/g, "").replace(/\s+/g, " ").trim();

const money = (v: number) => v.toLocaleString("he-IL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** A supermarket receipt. The page-load "print" is the one orchestrated
 *  animation on the site: receipts print in turn, totals count up, and the
 *  cheapest one gets the sale-tag stamp. */
export default function Receipt({ chainName, color, stores, lines, moreCount, total, isCheapest, premiumPct, index }: Props) {
  const delay = index * 180;
  return (
    <article
      className={`receipt${isCheapest ? " receipt-winner" : ""}`}
      style={{ ["--delay" as string]: `${delay}ms`, ["--chain" as string]: color }}
      aria-label={`${chainName}: סל של ${money(total)} ש"ח`}
    >
      <header className="receipt-head">
        <h3>{chainName}</h3>
        <span>{stores === 1 ? "סניף 1" : `${stores} סניפים`}</span>
      </header>
      <ul className="receipt-lines">
        {lines.map((l) => (
          <li key={l.name}>
            <span className="r-name">{cleanName(l.name)}</span>
            <span className="r-price">{money(l.price)}</span>
          </li>
        ))}
        <li className="r-more">ועוד {moreCount.toLocaleString("he-IL")} מוצרים</li>
      </ul>
      <footer className="receipt-total">
        <span>סה״כ</span>
        <strong>
          <CountUp value={total} delayMs={delay + 450} />
        </strong>
      </footer>
      {isCheapest ? (
        <span className="stamp">הכי זול</span>
      ) : (
        <p className="receipt-delta">{premiumPct != null ? `יקר ב-${premiumPct}%` : ""}</p>
      )}
    </article>
  );
}
