export const dynamic = "force-static";

/** Liveness probe: the web process is up. Does not check the backend. */
export function GET(): Response {
  return Response.json({ status: "ok", service: "aml-web", version: "0.0.0" });
}
