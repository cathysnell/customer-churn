// Genie Conversations API client — powers the Ask tab. We render the returned SQL +
// tabular result in our own UI (the "API panel" decision), so answers stay on-brand
// and provably match the dashboards. The parse helpers are pure and unit-tested; the
// orchestration (start → poll → fetch result) uses global fetch.

import type { AppConfig } from "./config.js";
import type { GenieAnswer } from "../shared/api.js";

type Json = Record<string, any>;

const POLL_INTERVAL_MS = 1200;
const POLL_TIMEOUT_MS = 60_000;

// ---- pure parse helpers (tested) ----

export function extractText(message: Json): string {
  const att = (message.attachments ?? []).find((a: Json) => a?.text?.content);
  return att?.text?.content ?? message?.content ?? "";
}

export function extractSql(message: Json): string {
  const att = (message.attachments ?? []).find((a: Json) => a?.query?.query);
  return att?.query?.query ?? "";
}

export function extractQueryAttachmentId(message: Json): string | null {
  const att = (message.attachments ?? []).find((a: Json) => a?.query);
  return att?.attachment_id ?? null;
}

/** Pick the substantive narrative text from a completed Genie message. Genie can emit
 *  a clarifying follow-up question as one text attachment and the real prose as another
 *  (and does not order them predictably), so we take the longest text attachment that
 *  isn't just a question, falling back to any text, then the message content. */
export function pickNarrativeText(message: Json): string {
  const texts: string[] = (message.attachments ?? [])
    .map((a: Json) => a?.text?.content)
    .filter((t: unknown): t is string => typeof t === "string" && t.trim().length > 0);
  if (texts.length === 0) return message?.content ?? "";
  const substantive = texts.filter((t) => !t.trim().endsWith("?"));
  const pool = substantive.length ? substantive : texts;
  return pool.reduce((a, b) => (b.length > a.length ? b : a));
}

export function parseStatementResult(payload: Json): {
  columns: string[];
  rows: (string | number | null)[][];
} {
  const sr = payload?.statement_response ?? payload;
  const columns: string[] = (sr?.manifest?.schema?.columns ?? []).map(
    (c: Json) => c.name,
  );
  const rows: (string | number | null)[][] = (sr?.result?.data_array ?? []).map(
    (r: any[]) => r.map((v) => (v === null || v === undefined ? null : v)),
  );
  return { columns, rows };
}

/** Tidy a Genie free-text answer for display in the plain-text narrative box:
 *  collapse whitespace/newlines, strip wrapping quotes, drop markdown emphasis
 *  markers, remove a trailing "…N rows shown" data-reference artifact, and keep the
 *  first couple of sentences under a length cap. Pure. */
export function cleanNarrative(text: string, maxLen = 520): string {
  let s = (text ?? "").replace(/\s+/g, " ").trim();
  s = s.replace(/^["'“”‘’]+|["'“”‘’]+$/g, "").trim();
  // Strip markdown emphasis (**bold**, *italic*, __bold__, _italic_) — the box renders plain text.
  s = s.replace(/\*\*(.+?)\*\*/g, "$1").replace(/__(.+?)__/g, "$1");
  s = s.replace(/\*(.+?)\*/g, "$1").replace(/_(.+?)_/g, "$1");
  // Drop a trailing "…across/in/based on N rows (shown)" reference to the query result.
  s = s.replace(/[,;]?\s*(across|in|based on|over|from)\s+(all\s+)?\d+\s+rows?(\s+\w+){0,2}(?=\.?\s*$)/i, "");
  s = s.replace(/\s+([.!?])/g, "$1").trim();
  // Keep at most the first two sentences.
  const parts = s.match(/[^.!?]+[.!?]+/g);
  if (parts && parts.length > 2) s = parts.slice(0, 2).map((p) => p.trim()).join(" ");
  // Hard length safety.
  if (s.length > maxLen) {
    const cut = s.slice(0, maxLen);
    const stop = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("! "), cut.lastIndexOf("? "));
    s = stop > maxLen * 0.4 ? cut.slice(0, stop + 1) : cut.trimEnd() + "…";
  }
  return s;
}

// ---- orchestration ----

let tokenCache: { token: string; exp: number } | null = null;

/** Bearer for the Genie REST calls: the PAT locally, or an OAuth M2M token minted
 *  from the app SP's client id/secret (cached until shortly before expiry). */
export async function getBearer(cfg: AppConfig): Promise<string> {
  if (cfg.token) return cfg.token;
  if (tokenCache && tokenCache.exp > Date.now() + 30_000) return tokenCache.token;
  const res = await fetch(`${cfg.host}/oidc/v1/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Authorization:
        "Basic " + Buffer.from(`${cfg.clientId}:${cfg.clientSecret}`).toString("base64"),
    },
    body: new URLSearchParams({ grant_type: "client_credentials", scope: "all-apis" }),
  });
  if (!res.ok) throw new Error(`oauth token failed: ${res.status}`);
  const j: Json = await res.json();
  tokenCache = { token: j.access_token, exp: Date.now() + (j.expires_in ?? 3600) * 1000 };
  return tokenCache.token;
}

function headers(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

function base(cfg: AppConfig): string {
  return `${cfg.host}/api/2.0/genie/spaces/${cfg.genieSpaceId}`;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Start a conversation and poll the message to completion. Returns the completed
 *  message plus the message URL + headers so callers can fetch attachments. */
async function runConversation(
  cfg: AppConfig,
  question: string,
): Promise<{ message: Json; msgUrl: string; h: Record<string, string> }> {
  const h = headers(await getBearer(cfg));
  const startRes = await fetch(`${base(cfg)}/start-conversation`, {
    method: "POST",
    headers: h,
    body: JSON.stringify({ content: question }),
  });
  if (!startRes.ok) throw new Error(`genie start failed: ${startRes.status}`);
  const start: Json = await startRes.json();
  const conversationId = start.conversation_id ?? start.conversation?.id;
  const messageId = start.message_id ?? start.message?.id;

  const msgUrl = `${base(cfg)}/conversations/${conversationId}/messages/${messageId}`;
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  let message: Json = {};
  for (;;) {
    const r = await fetch(msgUrl, { headers: h });
    if (!r.ok) throw new Error(`genie poll failed: ${r.status}`);
    message = await r.json();
    const status = message.status;
    if (status === "COMPLETED" || status === "FAILED") break;
    if (Date.now() > deadline) throw new Error("genie poll timed out");
    await sleep(POLL_INTERVAL_MS);
  }
  return { message, msgUrl, h };
}

export async function askGenie(
  cfg: AppConfig,
  question: string,
): Promise<GenieAnswer> {
  const { message, msgUrl, h } = await runConversation(cfg, question);

  let columns: string[] = [];
  let rows: (string | number | null)[][] = [];
  const attachmentId = extractQueryAttachmentId(message);
  if (attachmentId) {
    const qr = await fetch(`${msgUrl}/attachments/${attachmentId}/query-result`, {
      headers: h,
    });
    if (qr.ok) ({ columns, rows } = parseStatementResult(await qr.json()));
  }

  return {
    question,
    text: extractText(message),
    sql: extractSql(message),
    columns,
    rows,
  };
}

/** Ask Genie for a qualitative narrative and return just the substantive text. Skips
 *  the query-result fetch (we don't render rows here) and picks the narrative
 *  attachment rather than any clarifying follow-up. */
export async function askGenieNarrative(cfg: AppConfig, question: string): Promise<string> {
  const { message } = await runConversation(cfg, question);
  return pickNarrativeText(message);
}
