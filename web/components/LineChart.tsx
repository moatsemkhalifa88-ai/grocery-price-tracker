"use client";

import { useMemo, useRef, useState, type PointerEvent } from "react";

export type Series = {
  id: string;
  label: string;
  color: string; // CSS colour / var()
  points: { x: string; y: number }[]; // x = ISO date
  dashed?: boolean;
  band?: { x: string; lo: number; hi: number }[];
};

// Only serialisable props: this is a client component rendered from server
// pages, so it receives a format *name* rather than a function.
export type ValueFormat = "index" | "ils" | "int";

const FORMATTERS: Record<ValueFormat, (v: number) => string> = {
  index: (v) => v.toFixed(1),
  ils: (v) => `₪${v.toFixed(2)}`,
  int: (v) => v.toFixed(0),
};

type Props = {
  series: Series[];
  height?: number;
  yLabel?: string;
  valueFormat?: ValueFormat;
  /** shown instead of the chart until there are at least two days of data */
  emptyText?: string;
};

const W = 760;
const PAD = { top: 16, right: 92, bottom: 28, left: 48 };

function niceTicks(min: number, max: number, count = 5): number[] {
  if (min === max) return [min];
  const raw = (max - min) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(+v.toFixed(6));
  return out;
}

export default function LineChart({
  series,
  height = 300,
  yLabel,
  valueFormat = "index",
  emptyText = "הגרף יופיע אחרי יומיים של איסוף נתונים.",
}: Props) {
  const format = FORMATTERS[valueFormat];
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  const { xs, x, y, yTicks, plotH } = useMemo(() => {
    const allX = Array.from(new Set(series.flatMap((s) => s.points.map((p) => p.x)))).sort();
    const vals = series.flatMap((s) => [
      ...s.points.map((p) => p.y),
      ...(s.band ?? []).flatMap((b) => [b.lo, b.hi]),
    ]);
    let lo = Math.min(...vals);
    let hi = Math.max(...vals);
    if (hi - lo < 1e-6) {
      // flat series: give the axis some room so ticks don't repeat
      const pad = Math.max(Math.abs(hi) * 0.01, 0.5);
      lo -= pad;
      hi += pad;
    }
    const padY = (hi - lo) * 0.08;
    const ticks = niceTicks(lo - padY, hi + padY);
    const yMin = Math.min(ticks[0], lo - padY);
    const yMax = Math.max(ticks[ticks.length - 1], hi + padY);
    const h = height - PAD.top - PAD.bottom;
    const w = W - PAD.left - PAD.right;
    const idx = new Map(allX.map((d, i) => [d, i]));
    return {
      xs: allX,
      x: (d: string) => PAD.left + ((idx.get(d) ?? 0) / Math.max(allX.length - 1, 1)) * w,
      y: (v: number) => PAD.top + (1 - (v - yMin) / (yMax - yMin || 1)) * h,
      yTicks: ticks.filter((t) => t >= yMin && t <= yMax),
      plotH: h,
    };
  }, [series, height]);

  if (xs.length < 2) {
    return (
      <div className="chart-empty" role="note">
        <span className="chart-empty-line" aria-hidden />
        <p>{emptyText}</p>
      </div>
    );
  }

  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const svg = ref.current;
    if (!svg) return;
    const r = svg.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const w = W - PAD.left - PAD.right;
    const i = Math.round(((px - PAD.left) / w) * (xs.length - 1));
    setHover(i >= 0 && i < xs.length ? i : null);
  };

  const xLabelEvery = Math.max(1, Math.ceil(xs.length / 6));
  const hx = hover != null ? xs[hover] : null;
  const fmtDay = (d: string) => new Date(d).toLocaleDateString("he-IL", { day: "numeric", month: "numeric" });

  // end-of-line direct labels, nudged apart so they don't collide
  const ends = series
    .filter((s) => !s.dashed && s.points.length)
    .map((s) => ({ s, yy: y(s.points[s.points.length - 1].y) }))
    .sort((a, b) => a.yy - b.yy);
  for (let i = 1; i < ends.length; i++) if (ends[i].yy - ends[i - 1].yy < 13) ends[i].yy = ends[i - 1].yy + 13;

  return (
    <div className="chart" dir="ltr">
      <svg
        ref={ref}
        viewBox={`0 0 ${W} ${height}`}
        role="img"
        aria-label={yLabel ?? "line chart"}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} className="grid" />
            <text x={PAD.left - 8} y={y(t)} className="tick" textAnchor="end" dominantBaseline="middle">
              {format(t)}
            </text>
          </g>
        ))}
        {xs.map((d, i) =>
          i % xLabelEvery === 0 ? (
            <text key={d} x={x(d)} y={PAD.top + plotH + 18} className="tick" textAnchor="middle">
              {fmtDay(d)}
            </text>
          ) : null
        )}
        {series.map((s) =>
          s.band?.length ? (
            <path
              key={s.id + "-band"}
              d={
                s.band.map((b, i) => `${i ? "L" : "M"}${x(b.x)},${y(b.hi)}`).join("") +
                [...s.band].reverse().map((b) => `L${x(b.x)},${y(b.lo)}`).join("") +
                "Z"
              }
              fill={s.color}
              opacity={0.12}
            />
          ) : null
        )}
        {series.map((s) => (
          <path
            key={s.id}
            d={s.points.map((p, i) => `${i ? "L" : "M"}${x(p.x)},${y(p.y)}`).join("")}
            fill="none"
            stroke={s.color}
            strokeWidth={2}
            pathLength={s.dashed ? undefined : 1}
            className={s.dashed ? "line-dashed" : "line-draw"}
            strokeDasharray={s.dashed ? "5 4" : undefined}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}
        {ends.map(({ s, yy }) => (
          <text key={s.id + "-lbl"} x={W - PAD.right + 8} y={yy} className="direct" dominantBaseline="middle">
            <tspan fill={s.color}>●</tspan> {s.label}
          </text>
        ))}
        {hx && (
          <g>
            <line x1={x(hx)} x2={x(hx)} y1={PAD.top} y2={PAD.top + plotH} className="crosshair" />
            {series.map((s) => {
              const p = s.points.find((q) => q.x === hx);
              return p ? (
                <circle key={s.id} cx={x(hx)} cy={y(p.y)} r={4.5} fill={s.color} className="dot" />
              ) : null;
            })}
          </g>
        )}
        <rect x={PAD.left} y={PAD.top} width={W - PAD.left - PAD.right} height={plotH} fill="transparent" />
      </svg>
      {hx && (
        <div
          className="tooltip"
          style={{ left: `${(x(hx) / W) * 100}%`, transform: x(hx) > W * 0.6 ? "translateX(-105%)" : "translateX(8px)" }}
        >
          <div className="tooltip-title">{new Date(hx).toLocaleDateString("he-IL")}</div>
          {series
            .map((s) => ({ s, p: s.points.find((q) => q.x === hx) }))
            .filter((r) => r.p)
            .sort((a, b) => b.p!.y - a.p!.y)
            .map(({ s, p }) => (
              <div key={s.id} className="tooltip-row" dir="rtl">
                <span className="swatch" style={{ background: s.color }} />
                <span>{s.label}</span>
                <b>{format(p!.y)}</b>
              </div>
            ))}
        </div>
      )}
      {series.length > 1 && (
        <div className="legend" dir="rtl">
          {series
            .filter((s) => !s.dashed)
            .map((s) => (
              <span key={s.id}>
                <span className="swatch" style={{ background: s.color }} />
                {s.label}
              </span>
            ))}
          {series.some((s) => s.dashed) && (
            <span>
              <span className="swatch dashed" /> תחזית
            </span>
          )}
        </div>
      )}
    </div>
  );
}
