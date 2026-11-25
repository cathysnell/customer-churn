// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Every api call stays pending: these tests cover only the Overview's jump buttons, which
// render before any data arrives. A Proxy means new api methods don't break the mock.
vi.mock("../lib/api", () => ({
  api: new Proxy({}, { get: () => () => new Promise(() => {}) }),
}));

import App from "../App";

const selectedTab = () => screen.getByRole("tab", { selected: true });

describe("Overview jump buttons", () => {
  it("'Open the worklist' opens the Retention Worklist", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /open the worklist/i }));
    expect(selectedTab()).toHaveTextContent("Retention Worklist");
    expect(screen.getByRole("heading", { name: /who should we contact today/i })).toBeInTheDocument();
  });

  it("'Ask a question' opens the Ask view", () => {
    render(<App />);
    const ask = screen.getByRole("button", { name: /ask a question/i });
    expect(ask).toHaveClass("jump"); // same look as the worklist button
    fireEvent.click(ask);
    expect(selectedTab()).toHaveTextContent("Ask");
    expect(screen.getByRole("heading", { name: /ask the data anything/i })).toBeInTheDocument();
  });
});
