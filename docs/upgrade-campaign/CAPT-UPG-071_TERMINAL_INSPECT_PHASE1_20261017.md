# UPG-071: terminal.inspect as an independent governed operation

Date: 2026-10-17. This is an isolated review candidate.

## Trust boundary
Unlike per-request reclassification of terminal.exec, terminal.inspect
has its own ToolDescriptor, operation, capability name and static effect
class pure_read_only. ToolBroker still requires a matching capability
grant/lease, an exact scope and idempotent request identity. The argv
classifier and Git-hardening checks occur in the adapter, AFTER the
authority boundary; rejected commands fail before process dispatch.

## Execution safeguards
- Exact JSON argv, no shell. Hardened read-only classifier refuses
  unrecognized verbs, write flags, unsafe Git modes and outside-scope
  path operands.
- Executable resolved only from OS system binary directories; inherited
  caller PATH is not trusted. Process runs via bounded LocalProcessBackend
  with sanitized environment, timeout, process group and output limits.
- Git configured filters are probed with hardening, then explicit
  filter drivers disabled before read execution.
- Tool does not auto-grant an inspect capability, does not downgrade
  terminal.exec and cannot satisfy HumanApproval.

## Evidence
- Ten new adapter tests including real /bin/cat, real Git status and
  refusals for shells, write-argv and outside-scope files.
- Full selected readonly-argv, authenticated RuntimeCommandService
  tool-wiring and adapter suite: 84 passed.
- Focused Ruff correctness/import lint: passed.

## Remaining release prerequisites
The underlying classifier is a security-sensitive allowlist, NOT a
kernel-enforced sandbox. Hostile repository options, nonstandard OS
binaries, TOCTOU symlink swaps, distributed filesystem providers and
process-level side effects require independent threat review and tests.
No broad unattended use or automatic approval for production until
those gates and full GitHub security/contract suites are green.
