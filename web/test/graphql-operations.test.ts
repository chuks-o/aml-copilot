import { readFileSync } from "node:fs";

import type { ResultOf, VariablesOf } from "@graphql-typed-document-node/core";
import {
  assertInterfaceType,
  assertUnionType,
  buildSchema,
  Kind,
  parse,
  validate,
  type DocumentNode,
} from "graphql";
import { describe, expect, expectTypeOf, it } from "vitest";

import type { CaseQueueDocument, DecideCaseDocument } from "@/generated/graphql";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

const schema = buildSchema(read("../src/graphql/schema.graphql"));
const operationFiles = {
  "case-queue.graphql": read("../src/graphql/operations/case-queue.graphql"),
  "case-file.graphql": read("../src/graphql/operations/case-file.graphql"),
};
// Every ```graphql block in docs/graphql-queries.md, in order.
const docBlocks = [
  ...read("../../docs/graphql-queries.md").matchAll(/```graphql\n([\s\S]*?)```/g),
].map((m) => m[1] ?? "");

function operationNames(document: DocumentNode): string[] {
  return document.definitions.flatMap((d) =>
    d.kind === Kind.OPERATION_DEFINITION && d.name ? [d.name.value] : [],
  );
}

describe("operations", () => {
  it("are shown verbatim in docs/graphql-queries.md, in file order", () => {
    expect(docBlocks).toEqual(Object.values(operationFiles));
  });

  it("cover both screens", () => {
    expect(Object.values(operationFiles).flatMap((src) => operationNames(parse(src)))).toEqual([
      "CaseQueue",
      "CaseQueueUpdates",
      "CaseFile",
      "DecideCase",
      "CaseFileUpdates",
    ]);
  });

  it.each(Object.entries(operationFiles))("%s is valid against the schema", (_, src) => {
    expect(validate(schema, parse(src)).map((e) => e.message)).toEqual([]);
  });

  it("generate typed documents for urql", () => {
    // Compile-time assertions (checked by `make typecheck`): urql's hooks infer these
    // types from the generated documents, so a schema change breaks the callers.
    expectTypeOf<VariablesOf<typeof CaseQueueDocument>["first"]>().toEqualTypeOf<number>();
    expectTypeOf<ResultOf<typeof DecideCaseDocument>["decideCase"]["__typename"]>().toEqualTypeOf<
      "DecideCaseSuccess" | "VersionConflict" | "InvalidTransition"
    >();
  });
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
