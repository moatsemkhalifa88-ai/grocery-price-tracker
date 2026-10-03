import { pct } from "@/lib/format";

// Price direction is never colour-only: arrow + sign + colour.
export default function ChangeBadge({ value }: { value: number }) {
  const up = value > 0;
  return (
    <span className={`change ${up ? "up" : "down"}`} aria-label={up ? "עלייה" : "ירידה"}>
      {up ? "▲" : "▼"} <bdi dir="ltr">{pct(value)}</bdi>
    </span>
  );
}
