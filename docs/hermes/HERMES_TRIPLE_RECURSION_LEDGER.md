# Hermes Triple-Recursion Ledger

Three independent passes over the same claim: *"Hermes is integrated under CAPT
governance."* Each pass attempted to falsify the previous pass's conclusion.

## Pass 1 — Audit the inherited claim

Question: did Ling's work constitute a Hermes integration?

Method: read every changed file; trace every call path; search the entire
repository for `hermes|bridge|runner|khsb|ctp`; check whether the plugin loads;
check whether any tool is registered; diff the changed files against
`origin/main`.

Finding: **no.** No process boundary was ever crossed. The `capt-solo` plugin
fails to load against the authoritative repository, and `hermes tools | grep capt`
returns zero tools. The only test change was an integer.

Falsification attempted: could the plugin be working through a path not visible
in the source? Checked `hermes plugins list`, `hermes tools`, and the live
`agent.log` plugin-registration lines. `biocapt` registers 18 tools; `capt-solo`
registers none. Confirmed.

Verdict: **Ling's claim was unsupported.** Reverted.

## Pass 2 — Choose and build the correct shape

Question: is Mode B (bootstrap bridge) the right target, as previously directed?

Method: inspect the unmerged bridge branch; inspect the Hermes middleware
surface; compare against the frozen ADR-0120 trust posture; count the authority
paths each mode creates.

Finding: Mode B would place Hermes inside the trust boundary, create a second
authority path, and couple CAPT to a Hermes-internal hook on a runtime already
753 commits behind upstream. Mode A reuses the frozen boundary with zero contract
changes.

Falsification attempted: could Mode A be a disguised duplicate of the reference
driver — i.e. is the "real Hermes" actually just CAPT-local code? Checked: PID
recorded, exit code recorded, elapsed time 11.8 s (an in-process call would be
milliseconds), and the observation text is LLM-authored prose that the reference
driver's deterministic scanner cannot produce. Confirmed real.

Verdict: **Mode A.** ADR written after inspection, not before.

## Pass 3 — Attempt to break the proof

Question: does the passing suite actually prove governance, or only that code runs?

Method: adversarial tests plus destructive proofs.

| Attack | Outcome |
|---|---|
| Delete the driver and rerun the frozen suites | 51 + 51 pass — CAPT does not depend on Hermes |
| Run the same work order through the reference driver | identical CAPT semantics, distinct artifacts |
| Replay in a separate OS process | identical digest, zero re-execution |
| Feed 6 forged authoritative payloads | all rejected |
| Present a spoofed descriptor | rejected on digest mismatch |
| Expire / revoke / mis-scope the lease | dispatch blocked before launch |
| Request a write operation | blocked before Hermes is contacted |
| Submit the same run id twice | rejected |
| Starve the budget to 1 second | fails closed with a budget error, no fabricated result |
| Set `MY_API_KEY`, `SOME_TOKEN`, `AUTH_SECRET` in the parent | none reach the child, by name or value |
| Ask ClaimGuard to accept "The issue was fixed." | rejected |

Falsification attempted: is the "governance" merely the reference driver's code
path with a different label? No — the Hermes path spawns a real process, and the
removal proof shows the frozen suites are indifferent to the driver's existence,
which means the governance being exercised is the frozen runtime's, not the
driver's.

Falsification attempted: are the three initially-failing tests evidence of a
weakened suite? They were fixed at the source (registry record shape, contract
validation ordering, an unrealistic sub-millisecond budget) rather than by
loosening assertions. The write-capable-slice check was moved *before* contract
validation so the driver's own refusal fires first — a real ordering defect the
test caught.

Verdict: **conformance holds for the scope claimed.**

## Standing limitations carried forward

1. No per-model-turn interception inside the Hermes loop (Mode A by design).
2. No OS-level sandbox — containment is capability + policy + digest verification,
   not kernel enforcement.
3. The user-scope `capt-solo` Hermes plugin remains broken against the
   authoritative repository; out of scope, documented, untouched.
4. The unmerged bootstrap-bridge branch is neither adopted nor deleted.

None of these are represented as solved.
