import { describe, expect, it } from "@jest/globals";

import { createCasesApiClient } from "@/lib/cases-api";

describe("cases API client", () => {
  it("builds typed requests against the configured base URL", async () => {
    const seen: Request[] = [];
    const client = createCasesApiClient({
      baseUrl: "http://api.test",
      fetch: (request: Request) => {
        seen.push(request);
        return Promise.resolve(
          new Response(JSON.stringify({ items: [], next_cursor: null, total_estimate: 0 }), {
            headers: { "content-type": "application/json" },
          }),
        );
      },
    });

    const { data } = await client.GET("/cases", {
      params: { query: { status: "OPEN", limit: 20 } },
    });

    expect(seen.map((r) => r.url)).toEqual(["http://api.test/cases?status=OPEN&limit=20"]);
    expect(data?.total_estimate).toBe(0);
  });
});
