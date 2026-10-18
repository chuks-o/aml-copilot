// Jest config (`pnpm run test`, `make test`). Rationale: docs/decisions/0020-test-infrastructure.md.
// Two projects: plain Node for *.test.ts (resolvers, REST client, route handlers), jsdom for
// *.test.tsx (React components). ts-jest transpiles only; `make typecheck` type-checks.

/** @type {import('ts-jest').TsJestTransformerOptions} */
const tsJest = { tsconfig: "<rootDir>/tsconfig.jest.json" };

/** @type {import('jest').Config} */
const shared = {
  transform: { "^.+\\.tsx?$": ["ts-jest", tsJest] },
  moduleNameMapper: { "^@/(.*)$": "<rootDir>/src/$1" },
};

/** @type {import('jest').Config} */
const config = {
  projects: [
    {
      ...shared,
      displayName: "node",
      testEnvironment: "node",
      testMatch: ["<rootDir>/test/**/*.test.ts"],
    },
    {
      ...shared,
      displayName: "dom",
      testEnvironment: "jsdom",
      testMatch: ["<rootDir>/test/**/*.test.tsx"],
      setupFilesAfterEnv: ["<rootDir>/test/setup-dom.ts"],
    },
  ],
};

export default config;
