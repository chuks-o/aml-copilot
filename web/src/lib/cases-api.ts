// The only way web code calls the aml REST API. Types come from backend/openapi.yaml via
// `make codegen` (src/generated/cases-api.ts); see docs/decisions/0018-generated-clients.md.
import createClient, { type ClientOptions } from "openapi-fetch";

import type { paths } from "@/generated/cases-api";
import { CASES_API_URL } from "@/lib/config";

export type CasesApiClient = ReturnType<typeof createClient<paths>>;

export function createCasesApiClient(options: ClientOptions = {}): CasesApiClient {
  return createClient<paths>({ baseUrl: CASES_API_URL, ...options });
}
