// Project rules for openapi.yaml that Redocly's declarative assertions can't express.
// Enabled in ../redocly.yaml. Rationale: docs/decisions/0014-cases-api-contract.md.

const REQUIRED_ERRORS = ["429", "500", "503"];

/** Every POST must declare a required Idempotency-Key header. */
function postRequiresIdempotencyKey() {
  return {
    Operation(operation, ctx) {
      if (ctx.key !== "post") return;
      const pathParameters = ctx.parent?.parameters ?? [];
      const parameters = [...pathParameters, ...(operation.parameters ?? [])].map(
        (p) => ctx.resolve(p).node,
      );
      const key = parameters.find(
        (p) => p?.in === "header" && p.name?.toLowerCase() === "idempotency-key",
      );
      if (!key || key.required !== true) {
        ctx.report({
          message: "POST operations must declare a required Idempotency-Key header.",
          location: ctx.location.child("parameters"),
        });
      }
    },
  };
}

/** Every operation documents the errors any request can get: 429, 500 and 503. */
function everyOperationDeclaresErrors() {
  return {
    Operation(operation, ctx) {
      const codes = Object.keys(operation.responses ?? {});
      const missing = REQUIRED_ERRORS.filter((code) => !codes.includes(code));
      if (missing.length > 0) {
        ctx.report({
          message: `Operation must declare responses ${missing.join(", ")}.`,
          location: ctx.location.child("responses"),
        });
      }
    },
  };
}

export default function amlPlugin() {
  return {
    id: "aml",
    rules: {
      oas3: {
        "post-requires-idempotency-key": postRequiresIdempotencyKey,
        "every-operation-declares-errors": everyOperationDeclaresErrors,
      },
    },
  };
}
