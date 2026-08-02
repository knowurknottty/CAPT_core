# CAPT Runtime Contracts

Language-neutral contract source + reproducible TypeScript and Python bindings.

## Layout

```
contracts/
├── schema/            # CANONICAL source — JSON Schema 2020-12 (ADR-0101)
│   ├── common.schema.json
│   ├── mission.schema.json
│   ├── task.schema.json
│   ├── policy.schema.json
│   ├── capability.schema.json
│   ├── tool.schema.json
│   ├── evidence.schema.json
│   ├── verification.schema.json
│   ├── claim.schema.json
│   ├── driver.schema.json
│   ├── event.schema.json
│   ├── checkpoint.schema.json
│   └── index.json        # version + source digest
├── tools/             # generator (ADR-0102)
│   ├── schema_model.py
│   ├── build_spec.py
│   ├── emit_python.py
│   ├── emit_typescript.py
│   ├── generate.py
│   ├── check_drift.py
│   ├── ts_parity.mjs
│   └── templates/
├── generated/
│   ├── typescript/   # committed; src/ is the binding, dist/ is build output
│   └── python/       # committed; capt_contracts package
├── fixtures/          # cross-language parity cases
└── README.md
```

## Regenerate

```bash
python3 contracts/tools/generate.py
```

Output is deterministic (sorted traversal, no timestamps/paths/hostnames). Two
runs into different directories are byte-identical.

## Drift check (CI)

```bash
python3 contracts/tools/check_drift.py
```

Regenerates to a temp dir and fails if any committed binding differs from the
schema source. Run this in CI on every PR.

## Cross-language parity

```bash
cd contracts/generated/typescript && npm install && npm run build
node contracts/tools/ts_parity.mjs
```

Reads the same fixture files as the Python suite and asserts both validators
return identical error lists (including exact message text).

## Type checking (TS)

```bash
cd contracts/generated/typescript && tsc -p tsconfig.json --noEmit
```

## Why JSON Schema is normative

ADR-0101: a single neutral source prevents either language from becoming
authoritative. The generator consumes one `SchemaModel`; both emitters share
the same traversal, so a schema construct cannot compile in one language and
silently diverge in the other. Behavioral parity is proven by the shared
validation spec (`build_spec.py`) interpreted identically by both languages.
