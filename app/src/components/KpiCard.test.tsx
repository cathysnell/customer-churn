// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KpiCard } from "./KpiCard";
import { RiskBadge } from "./RiskBadge";

describe("KpiCard", () => {
  it("renders label, value, and the illustrative tag", () => {
    render(<KpiCard label="MRR at risk" value="$541,488" illustrative delta="down a bit" deltaDir="down" />);
    expect(screen.getByText("MRR at risk")).toBeInTheDocument();
    expect(screen.getByText("$541,488")).toBeInTheDocument();
    expect(screen.getByText("illustrative")).toBeInTheDocument();
  });

  it("omits the illustrative tag when not set", () => {
    render(<KpiCard label="Pro monthly churn" value="3.25%" />);
    expect(screen.queryByText("illustrative")).not.toBeInTheDocument();
  });
});

describe("RiskBadge", () => {
  it("renders the band with its severity class", () => {
    const { container } = render(<RiskBadge band="high" />);
    expect(screen.getByText("high")).toBeInTheDocument();
    expect(container.querySelector(".badge.high")).toBeTruthy();
  });
});
