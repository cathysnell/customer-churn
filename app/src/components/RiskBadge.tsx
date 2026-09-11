import type { RiskBand } from "../../shared/api";

const DOT: Record<RiskBand, string> = { high: "high", medium: "med", low: "low" };

export function RiskBadge({ band }: { band: RiskBand }) {
  return (
    <span className={`badge ${band}`}>
      <span className={`rk ${DOT[band]}`} />
      {band}
    </span>
  );
}
