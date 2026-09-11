import { useState } from "react";
import { Overview } from "./views/Overview";
import { Worklist } from "./views/Worklist";
import { Ask } from "./views/Ask";

type View = "overview" | "worklist" | "ask";
type Persona = "exec" | "am";
type Brand = "databricks" | "anysphere";

const TABS: { id: View; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "worklist", label: "Retention Worklist" },
  { id: "ask", label: "Ask" },
];

export default function App() {
  const [view, setView] = useState<View>("overview");
  const [persona, setPersona] = useState<Persona>("exec");
  const [brand, setBrand] = useState<Brand>("databricks");

  function pickPersona(p: Persona) {
    setPersona(p);
    setView(p === "exec" ? "overview" : "worklist");
  }
  function pickBrand(b: Brand) {
    setBrand(b);
    document.documentElement.dataset.brand = b;
  }

  return (
    <div className="app">
      <header className="appbar">
        <div className="brandmark">
          <span className="logo" aria-hidden>
            <svg viewBox="0 0 24 24" fill="none"><path d="M3 7.5 12 3l9 4.5M3 7.5 12 12l9-4.5M3 7.5v9L12 21l9-4.5v-9M12 12v9" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /></svg>
          </span>
          <div>
            <div className="name">Retention Cockpit</div>
            <div className="sub">{brand === "anysphere" ? "Anysphere" : "Databricks"} · dev_churn</div>
          </div>
        </div>

        <nav className="tabs" role="tablist" aria-label="Views">
          {TABS.map((t) => (
            <button key={t.id} className="tab" role="tab" aria-selected={view === t.id} onClick={() => setView(t.id)}>{t.label}</button>
          ))}
        </nav>

        <span className="spacer" />

        <div className="seg" role="group" aria-label="Persona">
          <span className="lab">View as</span>
          <button aria-pressed={persona === "exec"} onClick={() => pickPersona("exec")}>Executive</button>
          <button aria-pressed={persona === "am"} onClick={() => pickPersona("am")}>Account mgr</button>
        </div>
        <div className="seg" role="group" aria-label="Brand theme">
          <span className="lab">Theme</span>
          <button aria-pressed={brand === "databricks"} onClick={() => pickBrand("databricks")}>Databricks</button>
          <button aria-pressed={brand === "anysphere"} onClick={() => pickBrand("anysphere")}>Anysphere</button>
        </div>
        <span className="envbadge"><span className="dot" /> fevm · live</span>
      </header>

      <div className="safety">
        <svg viewBox="0 0 24 24" fill="none"><path d="M12 3l9 16H3L12 3z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M12 10v4M12 16.5v.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
        <span><b>Illustrative synthetic data</b> — no real customer data. Numbers mirror the governed metric views &amp; Genie space.</span>
      </div>

      <div className="wrap">
        {view === "overview" && <Overview persona={persona} onGoto={(v) => setView(v as View)} />}
        {view === "worklist" && <Worklist />}
        {view === "ask" && <Ask />}
      </div>
    </div>
  );
}
