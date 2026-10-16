import { readFileSync } from "node:fs";

import {
  assertInterfaceType,
  assertUnionType,
  buildSchema,
  Kind,
  parse,
  validate,
  type DocumentNode,
} from "graphql";
import { describe, expect, it } from "vitest";

const schema = buildSchema(
  readFileSync(new URL("../src/graphql/schema.graphql", import.meta.url), "utf8"),
);
const doc = readFileSync(new URL("../../docs/graphql-queries.md", import.meta.url), "utf8");

// Every ```graphql block in docs/graphql-queries.md, parsed.
const blocks: DocumentNode[] = [...doc.matchAll(/```graphql\n([\s\S]*?)```/g)].map((m) =>
  parse(m[1] ?? ""),
);

function operationNames(document: DocumentNode): string[] {
  return document.definitions.flatMap((d) =>
    d.kind === Kind.OPERATION_DEFINITION && d.name ? [d.name.value] : [],
  );
}

describe("docs/graphql-queries.md", () => {
  it("documents the operations of both screens", () => {
    expect(blocks.flatMap(operationNames)).toEqual([
      "CaseQueue",
      "CaseQueueUpdates",
      "CaseFile",
      "DecideCase",
      "CaseFileUpdates",
    ]);
  });

  it.each(blocks.map((block, i) => [operationNames(block).join(", "), i] as const))(
    "%s is valid against the schema",
    (_, i) => {
      const block = blocks[i];
      if (!block) throw new Error(`block ${String(i)} missing`);

      expect(validate(schema, block).map((e) => e.message)).toEqual([]);
    },
  );
});

describe("decideCase result", () => {
  it("is a union of success and the expected failures", () => {
    const members = assertUnionType(schema.getType("DecideCasePayload")).getTypes();

    expect(members.map((t) => t.name)).toEqual([
      "DecideCaseSuccess",
      "VersionConflict",
      "InvalidTransition",
    ]);
  });

  it("has every failure implement UserError", () => {
    const userError = assertInterfaceType(schema.getType("UserError"));
    const failures = schema.getPossibleTypes(userError).map((t) => t.name);

    expect(failures).toEqual(["VersionConflict", "InvalidTransition"]);
  });
});
