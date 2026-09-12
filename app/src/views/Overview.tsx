import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { KpiCard } from "../components/KpiCard";
import { BarList } from "../components/BarList";
import { TrendChart } from "../components/TrendChart";
import { moneyShort, pct, geoSeverity } from "../lib/format";
import type { RiskBand } from "../../shared/api";

const BAND_COLOR: Record<RiskBand, string> = {
  high: "var(--risk-high)",
  medium: "var(--risk-med)",
  low: "var(--risk-low)",
};
const BAND_DOT: Record<RiskBand, "high" | "med" | "low"> = { high: "high", medium: "med", low: "low" };

export function Overview({ onGoto }: { onGoto: (v: string) => void }) {
  const kpis = useAsync(() => api.kpis(), []);
  const trend = useAsync(() => api.trend(), []);
  const geo = useAsync(() => api.geoChurn(), []);

  const title = "Are we winning against the 4% churn target?";
  const lede =
    "Daily churn scoring across 50,000 Pro subscribers, rolled up to the KPIs the CRO and CFO manage — churn rate, revenue at risk, and program ROI.";

  const k = kpis.data;
  const churnUnder = k ? k.churnRatePct < k.churnTargetPct : false;
  const highBand = k?.mrrAtRiskByBand.find((b) => b.band === "high");
  const topGeo = geo.data?.[0];

  return (
    <section>
      <div className="pagehead">
        <div>
          <div className="eyebrow">Executive overview · Pro-tier retention</div>
          <h1>{title}</h1>
          <p className="lede">{lede}</p>
        </div>
      </div>

      {kpis.loading && <div className="state">Loading KPIs…</div>}
      {kpis.error && <div className="state err">Couldn’t load KPIs: {kpis.error}</div>}

      {k && (
        <div className="kpis">
          <KpiCard
            label="Pro monthly churn"
            value={pct(k.churnRatePct)}
            delta={`${churnUnder ? "▲ under" : "▼ over"} target · was ${k.churnBaselinePct}% baseline`}
            deltaDir={churnUnder ? "up" : "down"}
          >
            <div className="track">
              <div
                className="fill"
                style={{ width: `${Math.min(100, (k.churnRatePct / (k.churnTargetPct * 1.5)) * 100)}%`, background: churnUnder ? "var(--good)" : "var(--risk-high)" }}
              />
              <div className="tgt" style={{ left: `${(k.churnTargetPct / (k.churnTargetPct * 1.5)) * 100}%` }} />
            </div>
          </KpiCard>

          <KpiCard label="MRR at risk" value={moneyShort(k.mrrAtRiskTotal)} small
            delta={highBand ? `${moneyShort(highBand.mrr)} in the high-risk band` : undefined} deltaDir="down">
            <div className="microsplit" title="high / medium / low">
              {k.mrrAtRiskByBand.map((b) => (
                <span key={b.band} style={{ width: `${(b.mrr / k.mrrAtRiskTotal) * 100}%`, background: BAND_COLOR[b.band] }} />
              ))}
            </div>
            <div className="microlegend">
              {k.mrrAtRiskByBand.map((b) => (
                <span key={b.band}><i style={{ background: BAND_COLOR[b.band] }} />{b.band} {moneyShort(b.mrr)}</span>
              ))}
            </div>
          </KpiCard>

          <KpiCard label="CRM reactivation rate" value={pct(k.reactivationPct, 1)} illustrative
            delta={`▲ +22% vs ${k.reactivationBaselinePct}% baseline`}>
            <div className="track"><div className="fill" style={{ width: "80%" }} /></div>
          </KpiCard>

          <KpiCard label="Projected annual impact" value={moneyShort(k.projectedAnnualImpact)} small illustrative
            delta="ⓘ NRR lift + churn prevention">
            <div className="track"><div className="fill" style={{ width: "70%", background: "var(--brand)" }} /></div>
          </KpiCard>
        </div>
      )}

      <div className="grid2">
        <div className="card chart">
          <div className="card-h"><h2>Monthly Pro churn vs target</h2><span className="meta">churn_metrics_monthly</span></div>
          <div className="card-b">
            {trend.loading && <div className="state">Loading trend…</div>}
            {trend.error && <div className="state err">{trend.error}</div>}
            {trend.data && k && <TrendChart points={trend.data} targetPct={k.churnTargetPct} />}
            <div className="legend">
              <span><i style={{ background: "var(--brand)" }} />Monthly churn rate</span>
              <span><i className="dash" />Target {k ? pct(k.churnTargetPct, 1) : "4.0%"}</span>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-h"><h2>So what?</h2></div>
          <div className="card-b callout">
            <p className="big">
              We’re <b>{churnUnder ? "under" : "over"} the {k ? pct(k.churnTargetPct, 1) : "4%"} target</b> this month — but risk is concentrated.{" "}
              {highBand && <><span className="hl">{moneyShort(highBand.mrr)}</span> of MRR sits in the <b>high-risk</b> band</>}
              {topGeo && <>, with <b>{topGeo.geo}</b> churning fastest</>}.
            </p>
            <p className="big" style={{ marginTop: 14 }}>
              And <span className="hl">1,004</span> high-value subscribers are flagged high-risk with <b>zero CRM outreach</b> — the gap the retention play closes.
            </p>
            <button className="jump" onClick={() => onGoto("worklist")}>Open the worklist <span aria-hidden>→</span></button>
          </div>
        </div>
      </div>

      <div className="grid2b">
        <div className="card">
          <div className="card-h"><h2>MRR at risk by band</h2><span className="meta">currently-subscribed</span></div>
          <div className="card-b">
            {k && (
              <BarList
                items={k.mrrAtRiskByBand.map((b) => ({ label: b.band[0].toUpperCase() + b.band.slice(1), value: b.mrr, color: BAND_COLOR[b.band], dotClass: BAND_DOT[b.band] }))}
                max={Math.max(...(k.mrrAtRiskByBand.map((b) => b.mrr) ?? [1]))}
                format={moneyShort}
              />
            )}
          </div>
        </div>
        <div className="card">
          <div className="card-h"><h2>Churn by region</h2><span className="meta">latest month</span></div>
          <div className="card-b">
            {geo.loading && <div className="state">Loading…</div>}
            {geo.data && (
              <BarList
                items={geo.data.map((g) => ({ label: g.geo, value: g.churnRatePct, color: BAND_COLOR[geoSeverity(g.churnRatePct)] }))}
                max={Math.max(...(geo.data.map((g) => g.churnRatePct) ?? [1])) * 1.05}
                format={(v) => pct(v)}
              />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
