import { describe, expect, it } from "vitest";
import {
  cleanNarrative,
  extractQueryAttachmentId,
  extractSql,
  extractText,
  parseStatementResult,
  pickNarrativeText,
} from "./genie.js";

const message = {
  status: "COMPLETED",
  content: "raw content",
  attachments: [
    { attachment_id: "att_1", text: { content: "This month's Pro churn is 3.25%." } },
    { attachment_id: "att_2", query: { query: "SELECT MEASURE(`Churn rate`) ...", description: "latest churn" } },
  ],
};

describe("genie parse helpers", () => {
  it("extracts the text answer, preferring an attachment", () => {
    expect(extractText(message)).toBe("This month's Pro churn is 3.25%.");
    expect(extractText({ content: "fallback" })).toBe("fallback");
  });
  it("extracts the generated SQL", () => {
    expect(extractSql(message)).toContain("MEASURE(`Churn rate`)");
    expect(extractSql({ attachments: [] })).toBe("");
  });
  it("finds the query attachment id", () => {
    expect(extractQueryAttachmentId(message)).toBe("att_2");
    expect(extractQueryAttachmentId({ attachments: [{ text: { content: "x" } }] })).toBeNull();
  });
  it("parses a statement result into columns + rows", () => {
    const payload = {
      statement_response: {
        manifest: { schema: { columns: [{ name: "Month" }, { name: "churn_rate" }] } },
        result: { data_array: [["2026-08-01", "0.0325"], ["2026-07-01", null]] },
      },
    };
    expect(parseStatementResult(payload)).toEqual({
      columns: ["Month", "churn_rate"],
      rows: [["2026-08-01", "0.0325"], ["2026-07-01", null]],
    });
  });
  it("handles an empty/absent result", () => {
    expect(parseStatementResult({})).toEqual({ columns: [], rows: [] });
  });
});

describe("pickNarrativeText", () => {
  // Mirrors a real Genie message: a query attachment, a suggested-questions
  // attachment, a clarifying-question text attachment, then the real narrative.
  const msg = {
    content: "the prompt",
    attachments: [
      { query: { query: "SELECT ..." }, attachment_id: "a0" },
      { suggested_questions: {}, attachment_id: "a1" },
      { text: { content: "Would you prefer a breakdown by geography instead?" }, attachment_id: "a2" },
      { text: { content: "Risk is concentrated among high-risk non-power users; re-engage them first." }, attachment_id: "a3" },
    ],
  };
  it("picks the substantive narrative over a clarifying question", () => {
    expect(pickNarrativeText(msg)).toBe(
      "Risk is concentrated among high-risk non-power users; re-engage them first.",
    );
  });
  it("falls back to message content when there is no text attachment", () => {
    expect(pickNarrativeText({ content: "just content", attachments: [{ query: {} }] })).toBe("just content");
  });
});

describe("cleanNarrative", () => {
  it("collapses whitespace and strips wrapping quotes", () => {
    expect(cleanNarrative('  "Churn is concentrated\n  in the high-risk cohort."  ')).toBe(
      "Churn is concentrated in the high-risk cohort.",
    );
  });
  it("strips markdown emphasis and a trailing rows-reference artifact", () => {
    const raw =
      "Risk sits with **high-risk non-power users**. Re-engage them by driving _usage_, since engagement aligns with retention across all 5 rows shown.";
    expect(cleanNarrative(raw)).toBe(
      "Risk sits with high-risk non-power users. Re-engage them by driving usage, since engagement aligns with retention.",
    );
  });
  it("keeps at most the first two sentences", () => {
    expect(cleanNarrative("One. Two. Three. Four.")).toBe("One. Two.");
  });
  it("returns empty string for empty/absent input", () => {
    expect(cleanNarrative("")).toBe("");
    expect(cleanNarrative(undefined as unknown as string)).toBe("");
  });
  it("truncates at a sentence break under the cap", () => {
    const long = "First sentence is complete. " + "x".repeat(400);
    const out = cleanNarrative(long, 60);
    expect(out).toBe("First sentence is complete.");
  });
  it("hard-truncates with an ellipsis when there is no early sentence break", () => {
    const out = cleanNarrative("y".repeat(400), 50);
    expect(out.endsWith("…")).toBe(true);
    expect(out.length).toBeLessThanOrEqual(51);
  });
});
