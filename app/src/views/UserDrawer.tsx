import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { money } from "../lib/format";

// Pre-generated per-persona re-engagement drafts (decision #5: pre-generated, with a
// clean seam to swap in a live Agent Bricks / Foundation Model call later).
const DRAFTS: Record<string, string> = {
  startup_founder:
    "Hi — we noticed your team's usage dipped over the last month (coding hours down, fewer AI-assisted edits). If the multi-file agent or codebase-wide context would speed up how your team ships, I'd love to set up a 20-minute working session. Happy to review your Team plan too. — Your Cursor team",
  team_lead:
    "Hi — your team's activity has slowed recently and a few seats look under-used. Want me to walk your leads through the newest agent features and share a rollout template? I can right-size the Team plan to your active seats. — Your Cursor team",
  individual_dev:
    "Hey — saw your sessions have tapered off lately. If something's getting in the way of your flow, I'd like to hear it. Meanwhile, here are two features most devs miss that tend to bring people back. — Your Cursor team",
  freelancer:
    "Hey — noticed you've been in less this past month. If your project mix changed, we have flexible options so you only pay for what you use. Want a quick rundown of the latest agent workflow? — Your Cursor team",
  student:
    "Hey — hope the term's going well! Your usage dropped off recently. Your student plan stays active, and here are a couple of features worth a look for coursework. — Your Cursor team",
};

function Sparkline({ endTrend }: { endTrend: number }) {
  const decline = [4.2, 4.0, 3.9, 3.6, 3.2, 2.9, 2.7, Math.max(2.4, endTrend * 4)];
  const W = 380, H = 64, mx = Math.max(...decline), mn = Math.min(...decline);
  const X = (i: number) => 6 + ((W - 12) * i) / (decline.length - 1);
  const Y = (v: number) => H - 8 - ((H - 16) * (v - mn)) / (mx - mn || 1);
  const p = decline.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto" }}>
      <path d={p} fill="none" stroke="var(--risk-high)" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={X(decline.length - 1)} cy={Y(decline[decline.length - 1])} r={3.5} fill="var(--risk-high)" />
    </svg>
  );
}

export function UserDrawer({ userId, onClose }: { userId: string | null; onClose: () => void }) {
  const open = userId !== null;
  const detail = useAsync(() => (userId ? api.user(userId) : Promise.resolve(null)), [userId]);
  const [toast, setToast] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Lock the background page scroll while the drawer is open, so the wheel scrolls
  // the drawer body (not the greyed-out page behind it).
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  const u = detail.data;
  const dropPct = u ? Math.round((1 - u.codingTrend) * 100) : 0;
  const riskColor = u ? (u.band === "medium" ? "var(--risk-med)" : `var(--risk-${u.band})`) : undefined;

  async function logOutreach() {
    if (!u) return;
    await api.outreach(u.userId);
    setToast(`Outreach logged for ${u.userId} · demo — no external send`);
    setTimeout(() => setToast(""), 2600);
  }

  return (
    <>
      <div className={`scrim${open ? " open" : ""}`} onClick={onClose} />
      <aside className={`drawer${open ? " open" : ""}`} role="dialog" aria-modal="true" aria-label="Subscriber detail" aria-hidden={!open}>
        {u && (
          <>
            <div className="dwr-h">
              <div>
                <div className="uid" style={{ fontSize: 14 }}>{u.userId}</div>
                <div className="who">{u.persona} · {u.geo} · {u.plan}</div>
              </div>
              <button className="xbtn" onClick={onClose} aria-label="Close">×</button>
            </div>
            <div className="dwr-b">
              <div className="sig">
                <div className="cap">The decline signal · last 8 weeks</div>
                <div className="sigrow"><span style={{ fontSize: 13, color: "var(--muted)" }}>Daily coding hours, trending down</span><span className="v">▼ {dropPct}%</span></div>
                <Sparkline endTrend={u.codingTrend} />
              </div>
              <div className="statgrid">
                <div><div className="k">Churn risk</div><div className="v" style={{ color: riskColor }}>{u.band} · {u.score.toFixed(2)}</div></div>
                <div><div className="k">MRR (USD/mo)</div><div className="v">{money(u.mrr)}</div></div>
                <div><div className="k">Coding-hours trend</div><div className="v">{u.codingTrend.toFixed(2)}×</div></div>
                <div><div className="k">CRM touches 30d</div><div className="v" style={u.crmTouches === 0 ? { color: "var(--risk-high)" } : undefined}>{u.crmTouches}</div></div>
                <div><div className="k">AI acceptance</div><div className="v">{Math.round(u.avgAcceptanceRate * 100)}%</div></div>
                <div><div className="k">Sessions / wk</div><div className="v">{u.avgSessionFrequency.toFixed(1)}</div></div>
              </div>
              <div className="play">
                <div className="ph">Suggested re-engagement <span className="genie">drafted by Agent Bricks</span></div>
                <div className="msg">{DRAFTS[u.persona] ?? DRAFTS.individual_dev}</div>
                <div className="foot">
                  <button className="btnp" onClick={logOutreach}>Log outreach</button>
                  <button className="btns">Add to campaign</button>
                  <span style={{ fontSize: 11, color: "var(--muted)", marginLeft: "auto" }}>review before sending</span>
                </div>
              </div>
            </div>
          </>
        )}
        {detail.loading && <div className="state">Loading subscriber…</div>}
        {detail.error && <div className="state err">{detail.error}</div>}
      </aside>
      <div className={`toast${toast ? " show" : ""}`}>{toast}</div>
    </>
  );
}
