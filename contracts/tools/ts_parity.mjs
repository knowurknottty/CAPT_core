/**
 * Cross-language fixture parity runner (TypeScript side).
 *
 * Reads the SAME fixture files as the Python conformance suite and asserts the
 * generated TypeScript validator returns identical error lists. Any divergence
 * in validation behaviour or message text fails the build.
 *
 * Run: npm --prefix contracts/generated/typescript run build
 *      node contracts/tools/ts_parity.mjs
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const contractsDir = join(here, "..");
const srcIndex = join(contractsDir, "generated", "typescript", "src", "index.ts");

// Import the TypeScript source directly via a tiny on-the-fly transpile is not
// possible in plain node, so we require the built dist. The CI build step
// produces it; for local parity we build if missing.
import { existsSync } from "node:fs";
let indexModule;
const distIndex = join(contractsDir, "generated", "typescript", "dist", "index.js");
if (existsSync(distIndex)) {
  indexModule = distIndex;
} else {
  // Fall back to importing the source through tsx-like behaviour is unavailable;
  // instead require the test to build first. We surface a clear error.
  console.error(
    "dist/index.js not found. Run: npm --prefix contracts/generated/typescript run build",
  );
  process.exit(2);
}

const { validate, CONTRACT_SCHEMA_VERSION, knownTypes } = await import(indexModule);

const fixtureFiles = ["core_contracts.json", "capability_and_events.json"];

let total = 0;
let failed = 0;
const failures = [];

for (const file of fixtureFiles) {
  const path = join(contractsDir, "fixtures", file);
  const data = JSON.parse(readFileSync(path, "utf-8"));
  for (const testCase of data.cases) {
    total += 1;
    const errors = validate(testCase.type, testCase.value);
    const valid = errors.length === 0;

    if (valid !== testCase.expectValid) {
      failed += 1;
      failures.push(
        `${testCase.id}: expectValid=${testCase.expectValid} but got ${JSON.stringify(errors)}`,
      );
      continue;
    }

    if (testCase.expectedErrors !== undefined) {
      const expected = JSON.stringify(testCase.expectedErrors);
      const actual = JSON.stringify(errors);
      if (expected !== actual) {
        failed += 1;
        failures.push(`${testCase.id}: expected ${expected} but got ${actual}`);
      }
    }
  }
}

console.log(`contract schema version: ${CONTRACT_SCHEMA_VERSION}`);
console.log(`types known to TS binding: ${knownTypes().length}`);
console.log(`fixture cases: ${total}, failures: ${failed}`);

if (failed > 0) {
  for (const failure of failures) {
    console.error(`FAIL ${failure}`);
  }
  console.log(
    JSON.stringify({ failures: failed, cases: [] }),
  );
  process.exit(1);
}

// Machine-readable summary for the Python conformance test.
console.log(
  JSON.stringify({
    failures: 0,
    cases: fixtureFiles.flatMap((file) => {
      const data = JSON.parse(readFileSync(join(contractsDir, "fixtures", file), "utf-8"));
      return data.cases.map((c) => ({
        id: c.id,
        errors: validate(c.type, c.value),
      }));
    }),
  }),
);
