export interface BarItem {
  label: string;
  value: number;
  color: string; // a CSS var() expression
  dotClass?: "high" | "med" | "low";
}

export function BarList({
  items,
  max,
  format,
}: {
  items: BarItem[];
  max: number;
  format: (v: number) => string;
}) {
  const scale = max > 0 ? max : 1;
  return (
    <div className="bars">
      {items.map((d) => (
        <div className="bar" key={d.label}>
          <span className="bl">
            {d.dotClass && <span className={`rk ${d.dotClass}`} />}
            {d.label}
          </span>
          <span className="track2">
            <span
              className="f"
              style={{ width: `${Math.max(3, (d.value / scale) * 100)}%`, background: d.color }}
            />
          </span>
          <span className="bv num">{format(d.value)}</span>
        </div>
      ))}
    </div>
  );
}
