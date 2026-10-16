import { readFileSync } from "node:fs";

import { assertObjectType, buildSchema } from "graphql";
import { describe, expect, it } from "vitest";

import { resolvers } from "@/graphql/resolvers";

const schema = buildSchema(
  readFileSync(new URL("../src/graphql/schema.graphql", import.meta.url), "utf8"),
);

describe("graphql schema and resolvers", () => {
  it("declares the console queries", () => {
    expect(Object.keys(assertObjectType(schema.getQueryType()).getFields())).toEqual([
      "health",
      "cases",
      "case",
    ]);
  });

  it("returns exactly the fields the Health type declares", () => {
    const declared = Object.keys(assertObjectType(schema.getType("Health")).getFields());

    expect(Object.keys(resolvers.Query.health()).sort()).toEqual(declared.sort());
  });
});
