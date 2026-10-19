# CAPT F2 — Reproducible Adversarial Repair Receipt

- Repair origin commit 5cbe0ffe; rebased code commit dd832e30
- Branch: fix/black-swan-f2-verifier-reconciliation-20261019
- Baseline: 2ce53288f565cd387a1d7629b41690f9872b2a4b
- Rebased against fetched remote main 3ff7caee
- Matrix candidate: CAPT_MARCH_F2_CLAIM_MATRIX_v1_2_20261019.md
- Preregister SHA256: d296a85777805de6eb539f004bdf874963c8eebfab9f8c30d8fc9baa00035b4e

## Evidence log digests
- /Users/knowurknot/CAPT_core/.capt-evidence/marching-orders-20261019/F2-tests-2ce532-selected-baseline.log: SHA256 c874a421fddb1a9ca8170931df9f36c4f5adc6df734fdea2bd40978ccc9396e4
- /Users/knowurknot/CAPT_core/.capt-evidence/marching-orders-20261019/F2-tests-2ce532-red-adversarial.log: SHA256 1d44c58ef588cc1511d035128729ccf4b1b065d89bd684da2436dbd904d79ee0
- /Users/knowurknot/CAPT_core/.capt-evidence/marching-orders-20261019/F2-tests-2ce532-adversarial-green.log: SHA256 f9b3d42a9dcc156f337cf1bb1e4fef58fbc8705990fb49bd425f13801204e232
- /Users/knowurknot/CAPT_core/.capt-evidence/marching-orders-20261019/F2-tests-2ce532-final-targeted.log: SHA256 3b673cb9f65420b71a5aefb78ac2bbf94171936721e7955e68fc0df1ae428241
- /Users/knowurknot/CAPT_core/.capt-evidence/marching-orders-20261019/F2-runtime-broad-highfd-exclude-ts-fixture.log: SHA256 3d16ef7aa91fd8be23b4948cdea064bde93b1b5b07a2ad71b237f4b17b32002c
- /Users/knowurknot/CAPT_core/.capt-evidence/marching-orders-20261019/F2-runtime-wide-firstfailure-short.log: SHA256 4e2c7d572d91be2ef4fc90943ee5ebae90f60e9872b07a6f87f7b8b0b0f6d7e3

## Evidence classification
- CONFIRMED: two RED regressions reproduced and green after patch; post-rebase broad runtime/audit/primitives 1,823 passing, 14 environment skips and 12 outside-selection deselections; contract and Docker wiring 62 passing.
- UNVERIFIED: full-suite PASS, live runtime integration, live full replay, same-UID adversary, Swift installed-client behavior, independent verification acceptance.
- This receipt does not grant authority; separate user directive approves commit/push/merge/pull conditionally on green checks, but not runtime deployment or claim promotion.

## Post-rebase evidence

- Operation black-swan-f2-3ff-final-combined-regressions-20261019-85: closed, exit 0, 1823 passed, 14 skipped, 12 deselected.
- Operation black-swan-f2-contract-and-docker-verification-20261019-84: closed, exit 0, 62 passed.
- Operation black-swan-f2-check-drift-isolated-20261019-83: closed, exit 0, 11 generated files match source.
- TypeScript v5.9.3 was obtained from preexisting local npm cache and relocated outside generated source files.
