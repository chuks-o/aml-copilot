import { describe, expect, it } from "@jest/globals";
import { render, screen } from "@testing-library/react";

import Home from "@/app/page";

describe("home page", () => {
  it("shows the console heading and the empty state", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { level: 1, name: "AML Copilot" })).toBeInTheDocument();
    expect(screen.getByText(/nothing to investigate yet/i)).toBeInTheDocument();
  });
});
