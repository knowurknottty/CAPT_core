# CAPT F2 — Reproducible Adversarial Repair Receipt

- Repair commit: 5cbe0ffed3d5070da51de40acbd61feb6dd41611
- Branch: fix/black-swan-f2-verifier-reconciliation-20261019
- Baseline: 2ce53288f565cd387a1d7629b41690f9872b2a4b
- Remote main when written: 7e1182154a4086b74529b970d04bef3ece4f4442
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
- CONFIRMED: 2 intentional RED regressions and GREEN after patch; 117 selected passing; 1,734 broad passing with environmental Docker failure.
- UNVERIFIED: full-suite PASS, live runtime integration, live full replay, same-UID adversary, Swift installed-client behavior, independent verification acceptance.
- No external provider call, state-changing integration, runtime restart, deployment, branch push or merge was authorized by this receipt.
