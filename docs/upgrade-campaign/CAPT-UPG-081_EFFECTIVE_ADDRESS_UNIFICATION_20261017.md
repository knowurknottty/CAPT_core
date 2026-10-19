# CAPT-UPG-081 — effective IPv4 admission unification (candidate)

Date: 2026-10-17. Isolated CAPT Core branch; no production behavior claimed.

## Found from source and synthetic test
UPG-069 fixed the standalone egress Guardian by expanding IPv4-mapped,
6to4, Teredo and well-known NAT64 IPv6 addresses to their effective IPv4
destinations. The SSH and media adapter declarations still used distinct
ipaddress predicates and could give different answers. A concrete
media origin https://[64:ff9b::a9fe:a9fe] was accepted even though its
embedded IPv4 address was cloud metadata 169.254.169.254.

## Narrow remediation
Use the exact Guardian effective-address primitive in the host-side
media origin validator and SSH network policy checker. Require every
effective address to satisfy its respective policy. A caller cannot
admit the IPv6 envelope while denying the embedded IPv4 destination.
The Guardian remains standalone Python -c; its source, UPG-069 floor,
and persistent Guardian source digest are unchanged by this branch.

Private SSH targets remain possible only under explicitly configured
destination classes/CIDRs. Loopback-only local model providers and
provider endpoint classification are unchanged. A declared media origin
continues to be metadata admission; network dispatch requires the
separately governed provider adapter authorization.

## Verification
- New tests: 10 passed. Red-first: NAT64/6to4 encoded destinations
  demonstrated policy differences before the patch.
- New + existing SSH, media adapter and Guardian tests: 74 passed.
- Changed-file critical Ruff lint (E4/E7/E9/F/I): clean after
  formatting imports; full-repository lints may have older warnings.

## Scope and open assurance
- This harmonizes static literal-IP policy and SSH DNS-address admission;
  it does not prove every external HTTP client's redirect/DNS-rebinding
  behavior. External media downloads and Cloud Run/gVisor socket routing
  remain separate test gates.
- Do not reinterpret legitimate authorized local endpoints as hostile.
- Do not merge without GitHub security/contract/reviewer gates and
  reciprocal Core/Bot review.


## October 19, 2026 — alternate host parsing attack surface
The original media origin validator used ipaddress.ip_address but treated
all parsing failures as ordinary hostnames. On macOS, legacy numeric names
2130706433, 0x7f000001 and 127.1 were accepted by declaration while
AI_NUMERICHOST resolved them locally to 127.0.0.1; no HTTP requests were made.
Percent-encoded host components, empty userinfo, backslashes and Unicode
numeric lookalikes also permit cross-library URL/IDNA disagreement.

Media origin admission now rejects ambiguous numeric notation, non-ASCII
Unicode hostnames, percent-coded/userinfo/backslash authorities and localhost
subdomains. Internationalized names must be supplied as ASCII punycode.
Normal DNS hostnames (including numeric labels like 123.example.com) remain
permitted, with a caveat: runtime DNS and HTTP redirect targets still
require separate enforceable egress checking; declaration acceptance does
not imply arbitrary resolved addresses are safe.

Negative-first regression fixtures: fourteen legacy/authority cases
failed before the fix; additional Unicode/localhost fixtures were added.
The updated combined SSH, media and Guardian suite passed 95 tests;
Ruff critical lint and diff checks passed. Actual HTTP clients and
DNS-rebinding/redirect chains have not been exercised.
