# CAPT Functionality Matrix

## Operator surfaces on merged `main`

| Capability | CLI | TUI | Tk desktop | SwiftUI |
|---|---|---|---|---|
| runtime lifecycle | yes | status/control | yes | contract only |
| checkpoint/resume | yes | yes | yes | contract only |
| durable memory | yes | view/control | view/control | contract only |
| pinned authored-skill verify/list/show | yes | no | no | no |
| evidence/verification | yes | yes | yes | contract only |
| provider registry/health/model list | `capt-ui` operator CLI | yes | yes | contract only |
| model-selection foundation | `capt-ui` | yes | yes | contract only |
| CaveCAPT verbosity | `capt-ui` | yes | operator-layer dependent | contract only |
| human approve/deny | expert/runtime paths | yes | yes | contract only |
| live bounded provider generation | no | no on `main` | no | no |

## Active integration additions

PR #47 is the current operator/provider execution slice. It adds provider generation, prompt assembly/provenance, human-reviewed enhancement, response modes, requested context budgets, and current-run cognitive provenance to the TUI path.

PR #44 adds governed discovery; #46 hardens execution/recovery; #48 adds bounded Cohort coordination; #49 adds the fail-closed security infrastructure gate.

## Release-gate truth

The following must not be represented as completed merely because pieces exist:

- exact-terminal-head integrated-stack acceptance;
- installed-runtime/live-provider acceptance for intended provider paths;
- true process-boundary cross-model continuation with Model A replaced by Model B;
- durable Cohort persistence/reconstruction/evidence admission;
- security closure while #49 remains blocked;
- a shipped native desktop product.

## Authority boundary

Every UI and compatibility surface is a projection/control client. RuntimeService/EventStore remain authoritative.