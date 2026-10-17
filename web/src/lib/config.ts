export const GRAPHQL_URL = process.env.NEXT_PUBLIC_GRAPHQL_URL ?? "/api/graphql";

/** Base URL of the aml REST API, for server-side code (the GraphQL route). Not exposed to the browser. */
export const CASES_API_URL = process.env.AML_CASES_API_URL ?? "http://127.0.0.1:8000";
