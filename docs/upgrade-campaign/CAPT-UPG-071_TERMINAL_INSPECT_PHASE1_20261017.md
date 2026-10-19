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
- Sixteen new adapter tests including real /bin/cat, real Git status and
  refusals for shells, writes, symlink-following recursive options and outside-scope files.
- Full selected readonly-argv, authenticated RuntimeCommandService
  tool-wiring and adapter suite: 90 passed.
- Focused Ruff correctness/import lint: passed.

## Remaining release prerequisites
The underlying classifier is a security-sensitive allowlist, NOT a
kernel-enforced sandbox. Hostile repository options, nonstandard OS
binaries, TOCTOU symlink swaps, distributed filesystem providers and
process-level side effects require independent threat review and tests.
No broad unattended use or automatic approval for production until
those gates and full GitHub security/contract suites are green.

## Post-review symlink traversal hardening
Six negative-first tests verified that ls -LR, find -L, grep -R and du -L
could follow symlinks into outside directories despite initial operand scope
checks. Those flags now refuse in the canonical readonly_argv admission
policy. Ordinary grep -r remains accepted because it does not follow
symlinks encountered while recursively traversing directories. The
expanded tests are 90/90 green; this remains a defence in depth and
not a kernel-enforced filesystem jail.


## Independent Git configuration escape remediation (2026-10-19)
Git config --get --file=/outside bypassed operand-scoped reads.
Git can also read out-of-scope includes and worktree Git directories.
The terminal.inspect adapter now denies ALL Git invocations, including
Git status/log, until OS-enforced filesystem isolation is available.
Six refusal fixtures cover explicit and ambient Git config access. Git
remains accessible only via the separately governed terminal.exec path.
This is a deliberate reduction of claimed read-only coverage.


## 2026-10-19 indirect-file admission hardening
An adversarial inspection of the local adapter demonstrated that an original
negative rg --follow test passed only because ripgrep was absent from the
hard-coded trusted OS executable directories on that machine. The classifier
now explicitly refuses rg --follow and rg -L, and dedicated classifier-level
tests prove rejection without relying on executable availability. Additional
subprocess options that can read/write outside declared arguments are denied:
sort --random-source, sort --temporary-directory, sort -T, and
du --exclude-from / du -X.

The jq filter language supports includes/imports outside explicit file
operands, so terminal.inspect also refuses all jq argv and routes them to
separately authorized terminal.exec. This joins the existing all-Git
refusal. The revised selected suite passed 105 tests and Ruff critical lint.

This improves static grammar safety, not complete filesystem isolation:
remaining allowed host executables can be subject to symlink TOCTOU, implicit
system config reads, platform-specific flags and indirect file access. No
unattended production enablement or no-prompt filesystem authority is claimed.


## 2026-10-19 reusable classifier consistency
The downstream terminal.inspect adapter refused jq imports, but the
standalone readonly_argv.admit helper still returned a safe plan for jq
and external file/module cases. The classifier now also refuses jq as an
unknown unbounded-read command; tests no longer claim its import grammar
can be secured only by positional file checks. New admission tests and
the adapter/runtime suites passed 107/107. No filesystem isolation claim
is made.


## 2026-10-19 implicit sort scratch-write boundary
Even without output flags, sort can spill merge/sort scratch files into the
inherited TMPDIR, which is typically outside the declared filesystem root.
The reusable read-only classifier now refuses every sort command rather
than assuming this is a pure read. Normal sort execution remains available
through separate governed terminal.exec grants, not terminal.inspect.


## df scope parity
Explicit df filesystem operands undergo the same scope check as stat/du
instead of being omitted as if they were non-path operands. Metadata reads
outside filesystemScope are refused; no-operand df remains allowed.
