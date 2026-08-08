# Release Evidence

This page points to the proof that CAPT's claims are backed by real artifacts,
and how to inspect it yourself.

## The evidence directory

```text
release_evidence/
  v0.5/
    release-readiness.md               # overall v0.5 release verdict
    requirement-evidence-matrix.json   # claim -> evidence mapping
    test-matrix.md                     # what was tested
    final-wheel-manifest.json          # the shipped wheel + hash
    installed-model-operator/          # real installed-wheel model proof
    public-claim-audit-corrected.md    # public-claim accuracy audit
    branch-pr-disposition.md/json      # branch/PR disposition
```

Start with `release_evidence/v0.5/release-readiness.md`.

## How to see the proof yourself

1. **Run the automated suite** — every claim that is "Tested" is covered by it:

   ```zsh
   python3 -m pytest tests/ -q
   ```

2. **Inspect runtime evidence** — start the runtime and read authoritative state:

   ```zsh
   capt start --seed
   capt --json evidence
   ```

3. **Inspect the wheel** — verify the shipped artifact matches the manifest hash.

## What is and is not claimed

- **Proven:** local memory, EventStore replay, governed checkpoint/restart/
  resume, evidence/verification, ClaimGuard, and a **bounded read-only** real
  Hermes inspection executed through the installed wheel.
- **Not claimed:** unrestricted autonomous repository engineering driven by an
  external model. The strongest current model-facing proof is the bounded
  read-only inspection under `installed-model-operator/`.

## Live verification from the command line

`capt evidence` is the one command that answers "why does CAPT say this is
complete?": it shows the mission spec, recorded evidence, verification result,
and ClaimGuard disposition from authoritative runtime state.