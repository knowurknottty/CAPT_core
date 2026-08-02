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
const distIndex = join(contractsDir, "generated", "typescript", "dist", "index.js");

const { validate, CONTRACT_SCHEMA_VERSION, knownTypes } = await import(distIndex);

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
  process.exit(1);
}

console.log("TS PARITY: OK");
