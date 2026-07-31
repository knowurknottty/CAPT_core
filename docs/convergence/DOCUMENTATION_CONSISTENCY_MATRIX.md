# DOCUMENTATION_CONSISTENCY_MATRIX — Pass 4

Candidate `7b9bcf4`. Checks agreement across all public docs on key terms.

| Term | README | PUBLIC_ARCH | DESIGN | WHITEPAPER | API manifest | CLI | Consistent? |
|---|---|---|---|---|---|---|---|
| Version | 0.5.0 | v0.5 | (none) | v0.5.0 (L451) | 0.5.0 | n/a | ✅ |
| Package name | capt-solo | capt-solo | capt-solo | capt-solo | capt-solo | capt | ✅ |
| Repo identity | CAPT_core | CAPT Core | CAPT Core | CAPT Core | n/a | n/a | ✅ |
| Architecture | six pillars | six pillars | pillars | six pillars | six pillars | n/a | ✅ |
| Terminology Core/Solo | Core=Solo | Core/Solo distinct | Core/Solo | Core/Solo | n/a | n/a | ✅ |
| Spaces | not mentioned | not mentioned | not mentioned | not mentioned | not mentioned | n/a | ✅ (correctly absent) |
| Runtime adapters | not claimed shipped | "future adapter" | n/a | "adapter seam" | n/a | n/a | ✅ |
| Hermes | "no harness dependency" | "integration target, not dependency" | n/a | "not architectural dependency" | n/a | n/a | ✅ |
| ATE | referenced (ANTI_TOKEN doc) | n/a | n/a | n/a | n/a | n/a | ✅ |
| License | MIT | n/a | n/a | n/a | MIT | n/a | ✅ |

## Broken links
| Doc | Referenced by | Exists? |
|---|---|---|
| docs/security/RELEASE_SECURITY_REPORT_V0.5.md | README | ❌ MISSING (F5) |
| docs/release/RELEASE_VERIFICATION_V0.5.md | README | ❌ MISSING (F5) |
| capt_solo.components in manifest | release validator | ❌ MISSING (F7/F1) |

## Verdict
Terminology and version consistency: STRONG (no contradictions). Two broken
navigation links (F5) + one manifest gap (F7) are the only consistency defects.
All other terms agree across every document.
