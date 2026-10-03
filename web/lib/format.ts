const ils = new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS", minimumFractionDigits: 2 });
const num = new Intl.NumberFormat("he-IL");

export const money = (v: number | null | undefined) => (v == null ? "—" : ils.format(v));
export const int = (v: number | null | undefined) => (v == null ? "—" : num.format(v));
export const pct = (v: number | null | undefined, digits = 1) =>
  v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;

export function shortDate(iso: string | Date | null | undefined): string {
  if (!iso) return "—";
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return d.toLocaleDateString("he-IL", { day: "numeric", month: "numeric" });
}

export function longDate(iso: string | Date | null | undefined): string {
  if (!iso) return "—";
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return d.toLocaleDateString("he-IL", { day: "numeric", month: "long", year: "numeric" });
}
