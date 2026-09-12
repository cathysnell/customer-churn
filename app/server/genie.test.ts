import { describe, expect, it } from "vitest";
import {
  cleanNarrative,
  extractQueryAttachmentId,
  extractSql,
  extractText,
  parseStatementResult,
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

describe("cleanNarrative", () => {
  it("collapses whitespace and strips wrapping quotes", () => {
    expect(cleanNarrative('  "Churn is concentrated\n  in the high-risk cohort."  ')).toBe(
      "Churn is concentrated in the high-risk cohort.",
    );
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
