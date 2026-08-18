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

import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const contractsDir = join(here, "..");
const srcIndex = join(contractsDir, "generated", "typescript", "src", "index.ts");

// Import the TypeScript source directly via a tiny on-the-fly transpile is not
// possible in plain node, so we require the built dist. If it is missing we
// build it on the fly with the project's own tsc (hermetic: no external dep).
import { existsSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
let indexModule;
const tsDir = join(contractsDir, "generated", "typescript");
const distIndex = join(tsDir, "dist", "index.js");
if (existsSync(distIndex)) {
  indexModule = distIndex;
} else {
  // Build only what parity needs (emit to dist). Prefer a local tsc; fall back
  // to the system tsc (CI installs the generated package, local dev may use a
  // global tsc). If neither works we surface a clear error.
  const buildCmds = [
    ["npx", ["--prefix", tsDir, "tsc", "-p", join(tsDir, "tsconfig.json")]],
    ["tsc", ["-p", join(tsDir, "tsconfig.json")]],
  ];
  let built = false;
  for (const [cmd, args] of buildCmds) {
    try {
      execFileSync(cmd, args, { stdio: "ignore" });
      built = true;
      break;
    } catch (e) {
      // try next
    }
  }
  if (!built) {
    console.error(
      "dist/index.js not found and tsc build failed. Run: npm --prefix contracts/generated/typescript install && npm --prefix contracts/generated/typescript run build",
    );
    process.exit(2);
  }
  if (!existsSync(distIndex)) {
    console.error("dist/index.js still missing after build attempt.");
    process.exit(2);
  }
  indexModule = distIndex;
}

const { validate, CONTRACT_SCHEMA_VERSION, knownTypes } = await import(indexModule);

const fixtureFiles = readdirSync(join(contractsDir, "fixtures"))
  .filter((name) => name.endsWith(".json"))
  .sort();

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
