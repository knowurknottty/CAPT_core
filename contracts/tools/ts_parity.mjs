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

// Plain Node cannot import the TypeScript source directly. Always rebuild the
// generated TypeScript before parity so a stale dist/ tree can never make
// Python/TypeScript validation appear divergent after a schema change.
import { existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
let indexModule;
const tsDir = join(contractsDir, "generated", "typescript");
const distIndex = join(tsDir, "dist", "index.js");
const buildCmds = [
  ["tsc", ["-p", join(tsDir, "tsconfig.json")]],
  ["npx", ["--prefix", tsDir, "tsc", "-p", join(tsDir, "tsconfig.json")]],
];
let built = false;
for (const [cmd, args] of buildCmds) {
  try {
    execFileSync(cmd, args, { stdio: "ignore" });
    built = true;
    break;
  } catch (e) {
    // try next configured compiler path
  }
}
if (!built || !existsSync(distIndex)) {
  console.error(
    "TypeScript parity build failed. Install tsc or run the generated package build before parity.",
  );
  process.exit(2);
}
indexModule = distIndex;

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
