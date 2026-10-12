# CAPT Repository Review Depth Standard (RRDS-1)

**Status:** candidate integration in isolated CAPT worktree, pending CI/independent verification and merge. 2026-10-12.

## Epistemic contract

A repository can be **discovered**, **triaged**, **sampled**, **inventoried**, **deep-reviewed**, or **validated**. Never promote an item to a stronger state by rhetoric.

- **Discovered:** URL/name located; no meaningful code inspection.
- **Triaged:** metadata, README, license, root manifests, coarse structure inspected.
- **Sampled:** selected files or directories inspected; must disclose selection and omitted surface.
- **Inventoried:** every accessible directory and regular file recursively enumerated at a pinned commit, with explicit exclusions and unresolved symlinks. A directory listing alone is not a code review.
- **Deep-reviewed:** inventory complete; all source-bearing directories considered; cross-module/entrypoint/authority/dependency and integration paths traced to line-level evidence; material tests or reproductions executed when feasible; gate passed and residual blind spots named.
- **Validated:** actual scoped integration/build/test or runtime behavior independently reproduced against exact checked-out bytes. Deep review alone does not establish this.

## Mandatory G0-G7 sequence

G0. Freeze **the entire declared set of repository identities** (22 in the originating campaign), commit SHAs, objectives, threat or integration questions, resource and time budget. Record absent or inaccessible repositories. Reject moving-target default branches.

G1. Recursively census the **entire reachable source tree**, not just root and first-level child directories. Include nested packages, tests, plugins, adapters, scripts, build files, configuration, native code, generated files, vendored dependencies and symlink presence. The tool may exclude large generated/vendor subtrees only explicitly and must report each exclusion and its impact. Every path is accounted for as inventoried, excluded, unresolved, or unreadable.

G2. Build first-party architecture map: entrypoints, package boundaries, exported API surfaces, internal import/dependency graph, execution/call sites, data stores, network and process boundaries, permissions, system interactions, transitive dependencies, CI, build gates. Do not assume the README describes the live path.

G3. Use threat-driven traversal to follow each proposed cherry-pick **from caller to effect and back to witness**, crossing directory/module boundaries. Identify where the code actually implements the capability, not merely where a symbol is documented.

G4. Collect line-level receipts for every material claim: repository, commit, exact path, line range or symbol, relevant byte/hash identity, and whether the finding is observed/source-read/inferred/proposed. A search hit, file title, or model summary alone is not such a receipt.

G5. Execute relevant unit tests, lint, integration tests, and negative/security cases in disposable isolation if the environment allows. Record exact command, exit code, and known skips. When infeasible, mark NOT_RUN and state why; no fabricated CI/build claims.

G6. Run a negative-space audit: untouched directories, unanswered questions, disabled features, alternate invocation paths, platform-specific implementations, submodules, LFS, sparse checkout, ignored/untracked paths, license/redistribution concerns, incomplete docs or mismatched HEADs. For deep review, the receipt gate must pass for the declared in-scope first-party code. A path that remains unresolved means PARTIAL; do not silently waive.

G7. Publish the coverage ledger *before* conclusions. Each recommendation includes (a) exact source evidence, (b) integration boundary, (c) risk/license, (d) acceptance test, (e) scope limits. Aggregate report must show number of repos seen, directories enumerated, source directories inspected, files inspected, and unresolved exclusions. If a reviewer ran out of budget, publish PARTIAL with explicit continuation frontier.

## Mechanical gate

`scripts/capt_repo_audit_gate.py` is an offline reference implementation. It recursively inventories regular files, hashes bytes, records directory census/exclusions/symlinks, and checks `capt.rrds.inspection.v1` file evidence against the inventory. No symlinks are followed.

Example:

```zsh
python3 scripts/capt_repo_audit_gate.py inventory \
  --repo /path/to/repoA --output repoA-census.json
python3 scripts/capt_repo_audit_gate.py verify \
  --census repoA-census.json \
  --inspection repoA-inspection.json \
  --min-source-fraction 0.70 \
  --output repo-coverage-verdict.json
```

The observations file shape:

```json
{
  "schema": "capt.rrds.inspection.v1",
  "critical_paths": ["src/auth/token.py"],
  "inspected": [{
    "path": "src/auth/token.py",
    "sha256": "<digest from census>",
    "line_evidence": "L12-L36: inspected authorization branch",
    "node_evidence_ref": "node-evidence://<genuine-Node-receipt>"
  }]
}
```

The gate requires inspection receipts in **every direct source-bearing directory**, a declared review of all heuristic high-risk path candidates, and at least 70% source-file coverage by default. Any excluded subtree, symlink, inaccessible path, absent line evidence, or digest mismatch makes the deep-coverage verdict fail. **70% is only a configurable breadth floor, not a scientifically established sufficiency threshold.** The reviewer must still trace all security- and task-critical paths, and for a safety-sensitive task a stronger threshold is warranted.

### Limits and non-gameability

The script validates **coverage claims against an inventory**; a self-authored inspection receipt can still lie. For trusted process evidence, pair each inspected path and digest with CAPT Node journaled read evidence and independently verify that digest. Neither the gate nor even 100% file access proves correct comprehension, complete control-flow reasoning, or absence of vulnerabilities. Human/adversarial verification remains necessary.

The instrument does not clone GitHub repositories, discover their names, read files outside configured local roots, issue inference, install packages, or make network calls. The operator must arrange checked-out sources and verify HEAD identities; it must not read or overwrite live secrets or installed runtimes to expand scope.

## Hard stop

A reviewer who examined only one subdirectory of a repository may truthfully claim **sampled** but never **deep-reviewed**. If a 22-repo task exceeds available time or tokens, return the completed subset with its receipts and an exact pending frontier. Never replace missing evidence with speculation or an executive-summary impression.

## Rollout

1. Add census and coverage-verdict artifacts to the existing CAPT-UPG G0/G6/G7 gates.
2. Run the existing 22-repository dossier through this standard again, retaining old conclusions as *unverified hypotheses* until substantiated.
3. Add this tool and its tests to a disposable candidate worktree, run platform and CI checks, have an independent adversary attempt false-positive coverage claims, then promote only after operator review.
4. Use each completed dossier as a benchmark case for future CAPT agent skill evaluations; reward defensible evidence and penalize unjustified completeness claims.