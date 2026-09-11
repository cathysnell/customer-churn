import type { ReactNode } from "react";

export interface KpiCardProps {
  label: string;
  value: string;
  small?: boolean;
  delta?: string;
  deltaDir?: "up" | "down";
  illustrative?: boolean;
  children?: ReactNode; // e.g. a target track or micro split
}

export function KpiCard({ label, value, small, delta, deltaDir, illustrative, children }: KpiCardProps) {
  return (
    <div className="card kpi">
      <div className="label">
        {label}
        {illustrative && <span className="pill illus">illustrative</span>}
      </div>
      <div className={`val num${small ? " small" : ""}`}>{value}</div>
      {delta && <span className={`delta ${deltaDir ?? "up"}`}>{delta}</span>}
      {children}
    </div>
  );
}
