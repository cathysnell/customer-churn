import { describe, expect, it } from "vitest";
import {
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
