# CAPT-UPG-017: Desktop Provenance DAG / Provenance Lens

- **Campaign ID**: `CAPT-UPG-017`
- **Issue**: #84
- **Branch**: `upgrade/capt-upg-017-provenance-lens`
- **Disposition**: `IMPLEMENTED_PENDING_EXACT_HEAD_VERIFICATION`

## Implementation

`capt_ui/operator/provenance.py` builds a deterministic graph only from explicit identifiers and relations present in CAPT's shared authoritative/read-model projection:

- mission -> task;
- task -> approval;
- prompt assembly -> approval;
- task -> driver run;
- task/mission -> claim;
- evidence -> claim;
- evidence -> verification;
- verification -> claim;
- claim -> ClaimGuard/claim-decision projection when a recorded verdict exists;
- recorded cognitive provenance -> driver run/model target/prompt assembly when those explicit identities are present.

Missing relationships remain absent. Verification and claim decisions remain separate nodes. Graph construction computes a content digest and deterministic topological order; cycles are reported as integrity failures instead of hidden.

`desktop/provenance_lens.py` provides a real Tk/Aqua desktop view over authenticated runtime projections:

- node table by kind/identity;
- selected-node incoming/outgoing edge detail;
- graph authority/digest display;
- headless JSON mode for acceptance/automation.

`pyproject.toml` adds:

```text
capt-provenance = desktop.provenance_lens:main
```

## Tests authored

`tests/test_provenance_dag.py` covers:

1. evidence / verification / claim / decision separation;
2. no fabricated evidence edge to an unrelated claim;
3. deterministic graph digest/nodes/edges;
4. explicit cycle failure.

## Verification boundary

No exact-head execution is available from the connected environment. No pytest, installed-wheel, or rendered-GUI PASS is claimed.

Minimum evidence before owner-ready integration:

```bash
pytest tests/test_provenance_dag.py
capt-provenance --sock <socket> --token-file <token> --headless
```

plus installed-wheel import/launch and desktop smoke verification.
