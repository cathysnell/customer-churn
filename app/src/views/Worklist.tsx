import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { RiskBadge } from "../components/RiskBadge";
import { money, trendArrow, trendClass, trendLabel } from "../lib/format";
import { GEOS, RISK_BANDS, type RiskBand } from "../../shared/api";
import { UserDrawer } from "./UserDrawer";

export function Worklist() {
  const [band, setBand] = useState<RiskBand | "">("");
  const [geo, setGeo] = useState("");
  const [noCrm, setNoCrm] = useState(false);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [browseAll, setBrowseAll] = useState(false);
  const [reload, setReload] = useState(0);

  const [page, setPage] = useState(1);
  const PAGE_SIZE = 25;

  // The tab lands on the untouched-high-risk queue, streamed from the serving layer
  // (Lakebase when wired, warehouse fallback otherwise). "Browse all at-risk" switches
  // to the general filterable at-risk list from the warehouse.
  const rows = useAsync(
    () =>
      browseAll
        ? api.atRisk({ band: band || undefined, geo: geo || undefined, noCrm: noCrm || undefined, limit: 500 })
        : api.doNow(500),
    [browseAll, band, geo, noCrm, reload],
  );
  const doNowCount = useAsync(() => api.doNowCount(), []);
  const health = useAsync(() => api.health(), []);
  const source = health.data?.doNowSource ?? "warehouse";

  const visible = (rows.data ?? []).filter((u) => !q || u.userId.toLowerCase().includes(q.toLowerCase()));

  // Reset to page 1 whenever the filtered set changes.
  useEffect(() => setPage(1), [browseAll, band, geo, noCrm, q]);
  const total = visible.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageSafe = Math.min(page, totalPages);
  const pageRows = visible.slice((pageSafe - 1) * PAGE_SIZE, pageSafe * PAGE_SIZE);
  const from = total === 0 ? 0 : (pageSafe - 1) * PAGE_SIZE + 1;
  const to = Math.min(pageSafe * PAGE_SIZE, total);

  return (
    <section>
      <div className="pagehead">
        <div>
          <div className="eyebrow">Retention worklist · account manager</div>
          <h1>Who should we contact today?</h1>
          <p className="lede">At-risk Pro subscribers ranked for outreach. Start with the queue below — high-risk, still subscribed, and not yet touched.</p>
        </div>
      </div>

      {!browseAll && (
        <div className="donow">
          <span className="cnt num">{doNowCount.data ? doNowCount.data.count.toLocaleString("en-US") : "…"}</span>
          <span className="txt">
            <b>Do this now.</b> High-risk, currently-subscribed subscribers with <b>0 CRM touches</b> in 30 days.<br />
            <span className="sub">Sorted by MRR — the highest-value saves first. From the <span className="mono">untouched_at_risk_users</span> path.</span>
          </span>
        </div>
      )}

      <div className="filters">
        <label className="search">
          <svg viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.8" /><path d="m20 20-3.5-3.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search user id…" aria-label="Search user id" />
        </label>
        {browseAll ? (
          <>
            <select className="fsel" value={band} onChange={(e) => setBand(e.target.value as RiskBand | "")} aria-label="Risk band">
              <option value="">All bands</option>
              {RISK_BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
            <select className="fsel" value={geo} onChange={(e) => setGeo(e.target.value)} aria-label="Region">
              <option value="">All regions</option>
              {GEOS.map((g) => <option key={g} value={g}>{g}</option>)}
            </select>
            <button className="chip" aria-pressed={noCrm} onClick={() => setNoCrm((v) => !v)}>No CRM touch</button>
            <button className="chip" onClick={() => setBrowseAll(false)}>← Back to the priority queue</button>
            <span className={`srcpill ${source}`}>
              {source === "lakebase" ? "⚡ Served live from Lakebase" : "Served from warehouse"}
            </span>
          </>
        ) : (
          <>
            <span className={`srcpill ${source}`}>
              {source === "lakebase" ? "⚡ Served live from Lakebase" : "Served from warehouse"}
            </span>
            <button className="chip" onClick={() => setBrowseAll(true)}>Browse all at-risk →</button>
          </>
        )}
      </div>

      <div className="card tablecard">
        <div className="tblscroll">
          <table>
            <thead><tr>
              <th>User</th><th>Region</th><th>Persona</th><th>Plan</th>
              <th className="r">MRR (USD/mo)</th><th>Risk</th><th className="r">Coding hrs vs prior mo</th><th className="r">CRM 30d</th>
            </tr></thead>
            <tbody>
              {rows.loading && <tr><td colSpan={8} className="state">Loading subscribers…</td></tr>}
              {rows.error && <tr><td colSpan={8} className="state err">{rows.error}</td></tr>}
              {!rows.loading && total === 0 && <tr><td colSpan={8} className="state">No subscribers match these filters.</td></tr>}
              {pageRows.map((u) => (
                <tr key={u.userId} onClick={() => setSelected(u.userId)}>
                  <td className="uid">{u.userId}</td>
                  <td>{u.geo}</td>
                  <td className="mono" style={{ fontSize: 12.5 }}>{u.persona}</td>
                  <td className="mono" style={{ fontSize: 12.5 }}>{u.plan}</td>
                  <td className="r num">{money(u.mrr)}</td>
                  <td><RiskBadge band={u.band} /></td>
                  <td className="r"><span className={`trend ${trendClass(u.codingTrend)}`}>{trendArrow(u.codingTrend)} {trendLabel(u.codingTrend)}</span></td>
                  <td className={`r ${u.crmTouches === 0 ? "crm0" : ""}`}>{u.crmTouches === 0 ? "0 · none" : u.crmTouches}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {total > PAGE_SIZE && (
        <div className="pager">
          <span className="pinfo num">Showing {from}–{to} of {total}</span>
          <div className="pbtns">
            <button className="pbtn" disabled={pageSafe <= 1} onClick={() => setPage((p) => p - 1)}>← Prev</button>
            <span className="ppage num">Page {pageSafe} of {totalPages}</span>
            <button className="pbtn" disabled={pageSafe >= totalPages} onClick={() => setPage((p) => p + 1)}>Next →</button>
          </div>
        </div>
      )}

      <UserDrawer userId={selected} onClose={() => setSelected(null)} onLogged={() => setReload((n) => n + 1)} />
    </section>
  );
}
