import { useState } from "react";
import { api } from "../lib/api";
import type { GenieAnswer } from "../../shared/api";

const CHIPS = [
  "What is this month's Pro churn?",
  "Which regions are trending worse?",
  "Who are our most at-risk subscribers?",
  "How much MRR is at risk from high-risk subscribers?",
];

export function Ask() {
  const [question, setQuestion] = useState(CHIPS[0]);
  const [answer, setAnswer] = useState<GenieAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(q: string) {
    setQuestion(q);
    setLoading(true);
    setError(null);
    try {
      setAnswer(await api.ask(q));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <div className="pagehead">
        <div>
          <div className="eyebrow">Ask · Genie space “Subscription Churn Analytics”</div>
          <h1>Ask the data anything.</h1>
          <p className="lede">Natural-language questions over the same governed tables — so the answer matches the dashboard, every time.</p>
        </div>
      </div>

      <form className="askbar" onSubmit={(e) => { e.preventDefault(); ask(question); }}>
        <input className="qin mono" value={question} onChange={(e) => setQuestion(e.target.value)} aria-label="Ask a question" />
        <button className="askbtn" type="submit" disabled={loading}>{loading ? "Asking…" : "Ask"}</button>
      </form>

      <div className="qchips">
        {CHIPS.map((c) => <button key={c} className="chip" onClick={() => ask(c)}>{c}</button>)}
      </div>

      {loading && <div className="state">Genie is thinking…</div>}
      {error && <div className="state err">{error}</div>}

      {answer && !loading && (
        <div className="answer">
          {answer.text && <div className="ans-head">{answer.text}</div>}
          {answer.columns.length > 0 && (
            <div className="restable"><table>
              <thead><tr>{answer.columns.map((c, i) => <th key={c} className={i ? "r" : ""}>{c}</th>)}</tr></thead>
              <tbody>{answer.rows.map((r, ri) => (
                <tr key={ri}>{r.map((v, ci) => <td key={ci} className={ci ? "r num" : "uid"}>{v ?? "—"}</td>)}</tr>
              ))}</tbody>
            </table></div>
          )}
          {answer.sql && <pre className="sqlblock">{answer.sql}</pre>}
          <div className="matchnote">
            <svg viewBox="0 0 24 24" fill="none"><path d="M20 6 9 17l-5-5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>
            Resolved through the governed metric views &amp; trusted functions — the same numbers as the Overview.
          </div>
        </div>
      )}
    </section>
  );
}
