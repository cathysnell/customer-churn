// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// The view's data calls never resolve here: these tests only cover the "So what?" jump buttons,
// which render before any data arrives.
vi.mock("../lib/api", () => {
  const pending = () => new Promise(() => {});
  return { api: { kpis: pending, trend: pending, geoChurn: pending, doNowCount: pending, soWhat: pending } };
});

import { Overview } from "./Overview";

describe("Overview jump buttons", () => {
  it("'Open the worklist' goes to the Worklist tab", () => {
    const onGoto = vi.fn();
    render(<Overview onGoto={onGoto} />);
    fireEvent.click(screen.getByRole("button", { name: /open the worklist/i }));
    expect(onGoto).toHaveBeenCalledWith("worklist");
  });

  it("'Ask a question' goes to the Ask tab, styled like the worklist button and beside it", () => {
    const onGoto = vi.fn();
    render(<Overview onGoto={onGoto} />);
    const ask = screen.getByRole("button", { name: /ask a question/i });
    const worklist = screen.getByRole("button", { name: /open the worklist/i });
    expect(ask).toHaveClass("jump");
    expect(ask.parentElement).toBe(worklist.parentElement);
    fireEvent.click(ask);
    expect(onGoto).toHaveBeenCalledWith("ask");
  });
});
