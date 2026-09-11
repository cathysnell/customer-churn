import type { TrendPoint } from "../../shared/api";

// Monthly churn line vs a target reference line. One scale; labels name reached values.
export function TrendChart({ points, targetPct }: { points: TrendPoint[]; targetPct: number }) {
  const W = 680, H = 250, L = 44, R = 14, T = 16, B = 34;
  const x0 = L, x1 = W - R, y0 = T, y1 = H - B;
  const n = points.length;
  if (n === 0) return <div className="state">No trend data.</div>;

  const vals = points.map((p) => p.churnRatePct);
  const lo = Math.floor(Math.min(...vals, targetPct) - 0.5);
  const hi = Math.ceil(Math.max(...vals, targetPct) + 0.5);
  const X = (i: number) => x0 + ((x1 - x0) * i) / Math.max(n - 1, 1);
  const Y = (v: number) => y1 - ((y1 - y0) * (v - lo)) / (hi - lo || 1);

  const gridLines = [];
  for (let v = lo; v <= hi; v++) {
    gridLines.push(
      <g key={v}>
        <line x1={x0} y1={Y(v)} x2={x1} y2={Y(v)} stroke="var(--grid)" strokeWidth={1} />
        <text x={x0 - 8} y={Y(v) + 4} textAnchor="end" fontSize={11} fill="var(--muted)">{v}%</text>
      </g>,
    );
  }

  const pts = points.map((p, i) => [X(i), Y(p.churnRatePct)] as const);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  const area = `M${X(0)} ${y1} ${pts.map((p) => `L${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ")} L${X(n - 1)} ${y1} Z`;
  const last = pts[n - 1];
  const lastVal = vals[n - 1];

  const step = Math.max(1, Math.floor(n / 6));
  const xLabels = points.map((p, i) =>
    i % step === 0 || i === n - 1 ? (
      <text key={i} x={X(i)} y={H - 12} textAnchor="middle" fontSize={10.5} fill="var(--muted)">
        {p.month.slice(0, 7)}
      </text>
    ) : null,
  );

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Monthly churn, latest ${lastVal}% vs target ${targetPct}%`}>
      <defs>
        <linearGradient id="af" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="var(--brand)" stopOpacity={0.2} />
          <stop offset="1" stopColor="var(--brand)" stopOpacity={0} />
        </linearGradient>
      </defs>
      {gridLines}
      <line x1={x0} y1={Y(targetPct)} x2={x1} y2={Y(targetPct)} stroke="var(--risk-high)" strokeWidth={1.5} strokeDasharray="5 4" />
      <text x={x1} y={Y(targetPct) - 6} textAnchor="end" fontSize={10.5} fill="var(--risk-high)" fontWeight={600}>
        target {targetPct.toFixed(1)}%
      </text>
      <path d={area} fill="url(#af)" />
      <path d={line} fill="none" stroke="var(--brand)" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last[0]} cy={last[1]} r={4.5} fill="var(--brand)" stroke="var(--surface)" strokeWidth={2} />
      <text x={last[0]} y={last[1] - 12} textAnchor="end" fontSize={12} fontWeight={700} fill="var(--text)">
        {lastVal.toFixed(2)}%
      </text>
      {xLabels}
    </svg>
  );
}
