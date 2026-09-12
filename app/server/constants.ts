// Illustrative business constants from docs/project-brief.md. These are NOT real
// customer figures and are labeled "illustrative" wherever they surface in the UI.
// The churn rate and MRR at risk are NOT here — those come live from the metric views.

export const CHURN_TARGET_PCT = 4.0;
export const CHURN_BASELINE_PCT = 4.7; // illustrative
export const REACTIVATION_PCT = 9.8; // illustrative (+22% vs baseline)
export const REACTIVATION_BASELINE_PCT = 8.0; // illustrative
export const PROJECTED_ANNUAL_IMPACT = 2_580_000; // illustrative ROI, ≈ $2.58M

// ---- Overview "So what?" Genie narrative ----

/** How long a cached narrative stays fresh. The box updates ~weekly so viewers see a
 *  stable message until there's a meaningful amount of new data behind it. */
export const NARRATIVE_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

/** Cache key for the Overview narrative row in the Lakebase narrative table. */
export const SO_WHAT_CACHE_KEY = "overview_so_what";

/** The question posed to Genie. Deliberately asks for a qualitative read only — the
 *  authoritative figures are rendered from the governed KPI endpoints, so we never
 *  depend on (or display) Genie's own numbers here. */
export const SO_WHAT_PROMPT =
  "In one or two sentences, give an executive 'so what' interpretation of the current " +
  "Pro-tier subscriber churn situation and the single most important retention action " +
  "to focus on this month. Be concise and qualitative — do not quote specific dollar " +
  "amounts, percentages, or subscriber counts, and do not reference the query, the " +
  "underlying data, or the number of rows. Reply with the narrative only.";

/** Templated qualitative fallback when Genie / the cache is unavailable. Carries no
 *  numbers (those come from the governed endpoints) and shows no "Powered by Genie" pill. */
export const SO_WHAT_FALLBACK =
  "Risk is concentrated in the high-value cohort whose usage is falling fastest — " +
  "clearing the zero-touch, high-risk queue is the quickest retention lever this month.";
