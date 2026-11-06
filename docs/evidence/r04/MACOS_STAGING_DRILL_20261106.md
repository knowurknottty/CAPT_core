# macOS R0.4 staging deployment drill — two receipts and post-run audit

All tests operated on the staging prefix and staging identity only; no production cutover was authorized.

## Original run — 19/20, failed crash-restart assertion

- Source commit: `fac6ad0eb64ce6a52a40031af7551a92e530d337`
- UTC: `2026-11-06T17:23:31Z`; macOS 26.4.1
- Receipt: `macos_install_drill_20261106T172331Z.txt`; SHA-256 `6d9a0caba8ef5ade99089051124053423c28f572e636d3561160d103611bcd6f`
- Result: 19 pass, 1 fail (Drill B); drill sent SIGKILL to launchd service PID 97531 after approximately 959 ms of uptime. The macOS launchd unified log recorded 'exited due to SIGKILL | sent by bash' followed by 'service inactive', not a restart. This does NOT prove that a crash-class signal fails to restart the daemon.
- Audit defect: the original Drill D accepted any failed socket connection, including ENOENT on a missing socket.

## Corrected run — 20/20 script assertions, with independent cleanup exception

- Source commit: `edbe214bfca05ec9643ed4729b001ac96d32398c`
- UTC: `2026-11-06T17:31:25Z`; macOS 26.4.1
- Receipt: `macos_install_drill_20261106T173125Z.txt`; SHA-256 `ebdf71600e3ad9404b0b350812a59b257ae2faf482859988a06dcd38b5bb82d1`
- Script result: 20 passed, 0 failed, exit 0. A crash-class SIGSEGV caused launchd to replace PID 2198 with PID 2415 after 10 seconds, both as staging UID 450.
- Drill D's human positive-control connection succeeded; agent's connection to the live socket was refused with OS errno 13 (EACCES).
- Rollback, process revocation and launchd bootout succeeded. The receipt reports unchanged live CAPT process identities.

**Post-run independent Directory Services audit** found that the hidden `_captnodestg` user record (UID/GID 450, `/usr/bin/false`, `/var/empty`) still existed. Staging groups, launchd service, staging installation and operator paths were absent; no staging-UID processes remained. The original `cmd_uninstall` suppressed errors from `dscl . -delete /Users/_captnodestg`. An additional native administrator-authorized deletion attempt returned `eDSPermissionError (-14120)` and did not remove the record. A macOS privacy/Full Disk Access restriction is a plausible cause, **not yet independently proven**.

## Remediation and open gate

Core PR #254 commit `803d07525e283e7303a0c77e8c4e89fadc5fe005` changed the staging uninstaller to report Directory Services deletion errors and verify the account, groups, paths and plist are absent before returning success. Syntax passed, but this new cleanup behavior has NOT yet been proven in a fresh macOS privileged drill.

**Gate status: PARTIAL / BLOCKED ON MACOS USER-RECORD DELETION.** The service crash-restart and socket-denial checks passed, but full staging teardown did not. Production remains unchanged. Remove the specific disposable user record through an authorized local macOS administrator workflow and rerun the patched staging drill; do not bypass macOS privacy protections or delete `/var/empty`.
