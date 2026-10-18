import { describe, expect, it } from "@jest/globals";

import { GET } from "@/app/api/healthz/route";

describe("GET /api/healthz", () => {
  it("reports ok", async () => {
    const res = GET();

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: "ok", service: "aml-web", version: "0.0.0" });
  });
});
