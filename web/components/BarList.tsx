// Horizontal bars (server component). Value text stays in ink colours; the bar carries identity.
type Row = { id: string; label: string; value: number; color: string; note?: string; highlight?: boolean };

export default function BarList({ rows, format }: { rows: Row[]; format: (v: number) => string }) {
  const max = Math.max(...rows.map((r) => r.value), 0) || 1;
  return (
    <ul className="barlist">
      {rows.map((r) => (
        <li key={r.id} className={r.highlight ? "hl" : undefined} title={`${r.label}: ${format(r.value)}`}>
          <span className="bl-label">{r.label}</span>
          <span className="bl-track">
            <span className="bl-bar" style={{ width: `${(r.value / max) * 100}%`, background: r.color }} />
          </span>
          <span className="bl-value">{format(r.value)}</span>
          {r.note && <span className="bl-note">{r.note}</span>}
        </li>
      ))}
    </ul>
  );
}
