# Verify AI Work in Five Minutes

CAPT does not make an AI claim true. It makes the claim, the inspected subject,
the evidence, and the point at which that evidence stops applying visible.

This tutorial uses only local files. It blocks network primitives during the
run and writes every durable artifact beneath a directory you choose.

## 1. Install the candidate

From a CAPT Solo checkout:

```bash
python3 -m build
python3 -m venv /tmp/capt-tutorial-venv
/tmp/capt-tutorial-venv/bin/pip install --no-deps dist/capt_solo-0.5.0-py3-none-any.whl
```

The release verification process uses a fresh directory rather than the fixed
`/tmp` path above. The short path is used here only to make the walkthrough easy
to follow.

## 2. Inspect the installed runtime

```bash
/tmp/capt-tutorial-venv/bin/capt --json doctor
```

`doctor` imports each adoption profile, locates the plugin manifest and bundled
skills, and confirms that optional PULSE networking is disabled by default. It
does not initialize a runtime home.

## 3. Run the walkthrough with the installed Python

```bash
/tmp/capt-tutorial-venv/bin/python \
  examples/verification_first/run.py \
  --output /tmp/capt-verification-first
```

The script:

1. creates a tiny Git subject containing an AI-generated release summary;
2. checks two exact claims in that file;
3. records an `EvidenceRecord` tied to a Verified State Identity;
4. commits a local CTP receipt;
5. builds and validates a deterministic Context Pack and handoff;
6. changes the subject so one claim becomes false;
7. demonstrates that the old evidence remains inspectable but is no longer
   applicable to the changed state.

The expected final decision is:

```text
RUN_TARGETED_VERIFICATION
```

That decision is the important result. CAPT does not quietly reuse a successful
check after the subject changed.

## 4. Inspect the evidence

```bash
ls /tmp/capt-verification-first/*.json
python3 -m json.tool /tmp/capt-verification-first/summary.json
python3 -m json.tool /tmp/capt-verification-first/applicability.json
```

The output directory contains:

| Artifact | Meaning |
|---|---|
| `evidence.json` | claim, source, scope, confidence, and provenance |
| `verification-before.json` | exact state that passed |
| `receipt.json` | committed CTP transaction and journal integrity result |
| `context-pack.json` | canonical exchange artifact |
| `handoff.json` | deterministic resume artifact |
| `verification-after.json` | changed state and failed claim check |
| `applicability.json` | reason prior evidence cannot be reused |
| `summary.json` | compact, machine-readable outcome |

## What this proves—and what it does not

This run proves that the installed artifact can execute the declared Evidence,
Verification, Context, and Transaction profiles locally, and that a subject
change makes the earlier evidence inapplicable.

It does not prove that arbitrary AI output is correct, that a model is safe, or
that a future environment is equivalent. Those require claim-specific checks
and new evidence.
