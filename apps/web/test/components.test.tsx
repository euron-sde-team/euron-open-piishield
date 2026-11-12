// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { KeyRoundIcon } from "lucide-react";
import { afterEach, describe, expect, it } from "vitest";

import { EmptyState } from "@/components/empty-state";
import { KpiTile } from "@/components/kpi-tile";

afterEach(cleanup);

describe("KpiTile", () => {
  it("shows the label and value", () => {
    render(<KpiTile label="Total scans" icon={KeyRoundIcon} value={12} />);
    expect(screen.getByText("Total scans")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("renders skeletons while loading, hiding the value", () => {
    const { container } = render(<KpiTile label="Total scans" icon={KeyRoundIcon} value={12} loading />);
    expect(screen.queryByText("12")).not.toBeInTheDocument();
    expect(container.querySelectorAll("[data-slot='skeleton']").length).toBeGreaterThan(0);
  });
});

describe("EmptyState", () => {
  it("always explains itself and offers an action", () => {
    render(
      <EmptyState
        icon={KeyRoundIcon}
        title="No API keys yet"
        description="Create a key so an application can call the API."
        action={<button type="button">New key</button>}
      />,
    );
    expect(screen.getByText("No API keys yet")).toBeInTheDocument();
    expect(screen.getByText(/application can call/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New key" })).toBeInTheDocument();
  });

  it("never renders a bare empty state with no action when one is passed", () => {
    render(<EmptyState icon={KeyRoundIcon} title="Nothing here" description="Explanation." />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
