import { useState } from "react";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { RiskBadge } from "../components/RiskBadge";
import { money, trendArrow, trendClass } from "../lib/format";
import { GEOS, RISK_BANDS, type RiskBand } from "../../shared/api";
import { UserDrawer } from "./UserDrawer";

export function Worklist() {
  const [band, setBand] = useState<RiskBand | "">("");
  const [geo, setGeo] = useState("");
  const [noCrm, setNoCrm] = useState(false);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const rows = useAsync(
    () => api.atRisk({ band: band || undefined, geo: geo || undefined, noCrm: noCrm || undefined }),
    [band, geo, noCrm],
  );
  const doNow = useAsync(() => api.doNow(500), []);

  const visible = (rows.data ?? []).filter((u) => !q || u.userId.toLowerCase().includes(q.toLowerCase()));

  return (
    <section>
      <div className="pagehead">
        <div>
          <div className="eyebrow">Retention worklist · account manager</div>
          <h1>Who should we contact today?</h1>
          <p className="lede">At-risk Pro subscribers ranked for outreach. Start with the queue below — high-risk, still subscribed, and not yet touched.</p>
        </div>
      </div>

      <div className="donow">
        <span className="cnt num">{doNow.data ? doNow.data.length.toLocaleString("en-US") : "…"}</span>
        <span className="txt">
          <b>Do this now.</b> High-risk, currently-subscribed subscribers with <b>0 CRM touches</b> in 30 days.<br />
          <span className="sub">Sorted by MRR — the highest-value saves first. From the <span className="mono">untouched_at_risk_users</span> path.</span>
        </span>
      </div>

      <div className="filters">
        <label className="search">
          <svg viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.8" /><path d="m20 20-3.5-3.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search user id…" aria-label="Search user id" />
        </label>
        <select className="fsel" value={band} onChange={(e) => setBand(e.target.value as RiskBand | "")} aria-label="Risk band">
          <option value="">All bands</option>
          {RISK_BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
        <select className="fsel" value={geo} onChange={(e) => setGeo(e.target.value)} aria-label="Region">
          <option value="">All regions</option>
          {GEOS.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
        <button className="chip" aria-pressed={noCrm} onClick={() => setNoCrm((v) => !v)}>No CRM touch</button>
      </div>

      <div className="card tablecard">
        <div className="tblscroll">
          <table>
            <thead><tr>
              <th>User</th><th>Region</th><th>Persona</th><th>Plan</th>
              <th className="r">MRR</th><th>Risk</th><th className="r">Coding trend 30d</th><th className="r">CRM 30d</th>
            </tr></thead>
            <tbody>
              {rows.loading && <tr><td colSpan={8} className="state">Loading subscribers…</td></tr>}
              {rows.error && <tr><td colSpan={8} className="state err">{rows.error}</td></tr>}
              {!rows.loading && visible.length === 0 && <tr><td colSpan={8} className="state">No subscribers match these filters.</td></tr>}
              {visible.map((u) => (
                <tr key={u.userId} onClick={() => setSelected(u.userId)}>
                  <td className="uid">{u.userId}</td>
                  <td>{u.geo}</td>
                  <td className="mono" style={{ fontSize: 12.5 }}>{u.persona}</td>
                  <td className="mono" style={{ fontSize: 12.5 }}>{u.plan}</td>
                  <td className="r num">{money(u.mrr)}</td>
                  <td><RiskBadge band={u.band} /></td>
                  <td className="r"><span className={`trend ${trendClass(u.codingTrend)}`}>{trendArrow(u.codingTrend)} {u.codingTrend.toFixed(2)}×</span></td>
                  <td className={`r ${u.crmTouches === 0 ? "crm0" : ""}`}>{u.crmTouches === 0 ? "0 · none" : u.crmTouches}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <UserDrawer userId={selected} onClose={() => setSelected(null)} />
    </section>
  );
}
