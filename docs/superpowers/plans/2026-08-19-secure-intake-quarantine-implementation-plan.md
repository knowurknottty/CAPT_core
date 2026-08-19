# Secure Intake / Quarantine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Accept arbitrary regular-file uploads as hostile opaque bytes, scan them inside a bounded quarantine boundary, and require explicit user disposition before they become context-eligible.

**Architecture:** A Python Operator Plane quarantine store owns opaque bytes and manifests. All format parsing/scanner execution occurs in a dedicated child worker launched under a deny-by-default macOS sandbox profile when the platform primitive is available; absence of the isolation primitive degrades the scan to `INCOMPLETE_SCAN` rather than silently weakening isolation. Swift only selects files and renders scan/disposition state; it never sends picker paths or unscanned bytes to models.

**Tech Stack:** Python stdlib (`hashlib`, `json`, `pathlib`, `subprocess`, `zipfile`, `tarfile`, `stat`, `secrets`, `os`, `resource`); `/usr/bin/file`; macOS `/usr/bin/sandbox-exec` when available; optional installed `clamscan`, `yara`, `exiftool`; existing CAPT Artifact/Workspace containment helpers; Swift 6/SwiftUI; pytest; Swift tests.

**Spec:** `docs/superpowers/specs/2026-08-19-public-release-quarantine-projects-council-design.md` Parts I §§4-13.

## Global Constraints

- No file-extension allowlist for ordinary regular files.
- Directories/repos use Workspace selection instead of upload semantics.
- Symlinks, sockets, FIFOs, devices, and other special nodes are rejected as upload sources.
- Original bytes are immutable after intake and stored without execute bits.
- Scanner failure/unavailability/isolation degradation yields uncertainty, never `clean`.
- Scanner workers receive no provider/API credentials.
- Network access is denied by the scanner sandbox; if CAPT cannot establish that boundary, external format/scanner execution is not treated as a complete scan.
- Archive derived content stays under `derived/` with traversal/symlink/bomb ceilings.
- Image/media metadata authenticity is never inferred from structural validity alone.
- Steganography output uses indicator/coverage language only.
- Scan completion does not grant context permission.

---

## File Structure

**Create:**
- `capt_ui/operator/quarantine.py` — storage, manifest, state machine, disposition, `FileReference`.
- `capt_ui/operator/quarantine_scan.py` — scan orchestration, adapter inventory, sandbox launcher.
- `capt_ui/operator/quarantine_worker.py` — isolated worker entrypoint; reads one quarantined blob and writes one bounded JSON result.
- `capt_ui/operator/quarantine_archive.py` — ZIP/TAR inspection and bounded derived extraction.
- `capt_ui/operator/quarantine_media.py` — image/media metadata + stego indicator helpers.
- `tests/capt_ui/test_quarantine.py`
- `tests/capt_ui/test_quarantine_scan.py`
- `tests/capt_ui/test_quarantine_archive.py`
- `tests/capt_ui/test_quarantine_media.py`
- `capt_ui/surfaces/desktop_swift/Sources/CAPTCoreDesktop/CAPTQuarantineModels.swift`
- `capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/AttachmentQuarantineView.swift`
- `capt_ui/surfaces/desktop_swift/Tests/CAPTCoreDesktopTests/CAPTQuarantineModelsTests.swift`

**Modify:**
- current `capt-ui` CLI entrypoint: add `quarantine ingest|scan|show|disposition|delete`.
- `CAPTOperatorCLI.swift`: typed wrappers for those operations.
- `CAPTOperatorStore.swift`: selected/scanning/awaiting-disposition attachment state.
- `ChatView.swift`: attachment entrypoint/card only; no scanner/domain logic.

---

### Task 1: Hostile opaque intake store

**Interfaces:**
- Produces `QuarantineStore.ingest(source: Path) -> QuarantineRecord`.
- Produces `QuarantineStore.blob_path(upload_id) -> Path`.

- [ ] **Step 1: Write RED intake tests**

```python
from pathlib import Path
import stat
import pytest
from capt_ui.operator.quarantine import QuarantineError, QuarantineStore


def test_ingest_copies_regular_file_to_opaque_private_location(tmp_path: Path):
    src = tmp_path / "evil name.txt"
    src.write_bytes(b"CAPT upload")
    store = QuarantineStore(tmp_path / "state")
    record = store.ingest(src, now="2026-08-19T00:00:00Z")

    assert record.original_name == "evil name.txt"
    assert record.state == "STORED_OPAQUE"
    assert record.sha256 == "sha256:6312088393c2e311ca6aceeb113846eb38ae88ec0be5a60305cd42ae9812bfd5"
    blob = store.blob_path(record.upload_id)
    assert blob.name == "blob"
    assert blob.read_bytes() == b"CAPT upload"
    assert stat.S_IMODE(blob.stat().st_mode) == 0o600
    assert stat.S_IMODE(blob.parent.parent.stat().st_mode) == 0o700


def test_ingest_rejects_directory_and_symlink(tmp_path: Path):
    store = QuarantineStore(tmp_path / "state")
    with pytest.raises(QuarantineError, match="regular file"):
        store.ingest(tmp_path)
    target = tmp_path / "target"; target.write_bytes(b"x")
    link = tmp_path / "link"; link.symlink_to(target)
    with pytest.raises(QuarantineError, match="regular file"):
        store.ingest(link)
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/capt_ui/test_quarantine.py -q
```

- [ ] **Step 3: Implement minimal store including atomic manifest writer**

```python
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import json, os, secrets, stat, tempfile

class QuarantineError(RuntimeError): pass

@dataclass(frozen=True)
class QuarantineRecord:
    schema_version: str
    upload_id: str
    original_name: str
    sha256: str
    byte_count: int
    state: str
    created_at: str

class QuarantineStore:
    def __init__(self, state_root: Path):
        self.root = Path(state_root) / "quarantine"

    def blob_path(self, upload_id: str) -> Path:
        return self.root / upload_id / "original" / "blob"

    def _atomic_json(self, target: Path, payload: dict) -> None:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, tmp_name = tempfile.mkstemp(prefix=".manifest-", dir=target.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp_name, target)
            os.chmod(target, 0o600)
        finally:
            if os.path.exists(tmp_name): os.unlink(tmp_name)

    def ingest(self, source: Path, *, now: str) -> QuarantineRecord:
        source = Path(source)
        st = source.lstat()
        if not stat.S_ISREG(st.st_mode):
            raise QuarantineError("upload source must be a regular file")
        upload_id = "upl-" + secrets.token_hex(16)
        root = self.root / upload_id
        original = root / "original"
        original.mkdir(parents=True, mode=0o700)
        os.chmod(root, 0o700); os.chmod(original, 0o700)
        digest = sha256(); byte_count = 0
        blob = original / "blob"
        with source.open("rb") as src, blob.open("xb") as dst:
            while chunk := src.read(1024 * 1024):
                digest.update(chunk); byte_count += len(chunk); dst.write(chunk)
        os.chmod(blob, 0o600)
        record = QuarantineRecord("1.0.0", upload_id, source.name, "sha256:" + digest.hexdigest(), byte_count, "STORED_OPAQUE", now)
        self._atomic_json(root / "manifest.json", asdict(record))
        return record
```

- [ ] **Step 4: Add FIFO/special-node tests and run GREEN**

Use `os.mkfifo` when supported; assert rejection. Assert source filename never becomes a directory component under quarantine.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/operator/quarantine.py tests/capt_ui/test_quarantine.py
git commit -m "feat(intake): add opaque quarantine storage"
```

---

### Task 2: Sandboxed scanner worker boundary

**Interfaces:**
- Produces `SandboxPolicy.build(blob, scan_dir, temp_dir) -> str`.
- Produces `run_scanner_worker(...) -> WorkerResult`.
- Worker stdin carries JSON config; stdout carries one bounded JSON result; no inherited secrets.

- [ ] **Step 1: Write RED isolation tests**

Test launcher environment equals an allowlist (`PATH`, `TMPDIR`, `LANG`) and excludes `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `CAPT_PROVIDER_KEY_*`, `SSH_AUTH_SOCK`. Assert command uses argument array and `shell=False`.

- [ ] **Step 2: Implement macOS sandbox profile**

Generate a Seatbelt profile equivalent to:

```text
(version 1)
(deny default)
(allow process*)
(allow sysctl-read)
(allow file-read* (literal "<blob>") (subpath "/usr") (subpath "/System"))
(allow file-write* (subpath "<scan-dir>") (subpath "<temp-dir>"))
(deny network*)
```

Escape literal paths for the profile; never interpolate into a shell command. Launch:

```python
argv = ["/usr/bin/sandbox-exec", "-p", profile, sys.executable, "-m", "capt_ui.operator.quarantine_worker"]
```

with `subprocess.run(..., shell=False, timeout=limits.wall_seconds, env=sanitized_env, input=config_json, text=True, capture_output=True)`.

- [ ] **Step 3: Add resource ceilings**

Use child `preexec_fn` only on supported POSIX execution to set `RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_FSIZE`, and `RLIMIT_NPROC` to configured ceilings. The worker also enforces max output bytes before returning.

- [ ] **Step 4: Fail closed when isolation cannot be established**

If `/usr/bin/sandbox-exec` is absent or sandbox launch fails before worker execution, emit adapter/isolation status `sandbox_unavailable`/`scanner_error`; top-level scan cannot exceed `INCOMPLETE_SCAN`. Do not silently rerun external parsers unsandboxed.

- [ ] **Step 5: Run tests and commit**

```bash
python -m pytest tests/capt_ui/test_quarantine_scan.py -q
git add capt_ui/operator/quarantine_scan.py capt_ui/operator/quarantine_worker.py tests/capt_ui/test_quarantine_scan.py
git commit -m "feat(intake): isolate quarantine scanner worker"
```

---

### Task 3: Common scan vocabulary and byte identification

**Interfaces:**
- Produces `ScanLimits`, `AdapterResult`, `ScanReport`, `scan_upload()`.
- Adapter states exactly: `not_installed`, `not_applicable`, `passed_without_indicator`, `indicator_found`, `scanner_error`.

- [ ] **Step 1: Write RED scan-report tests**

```python
def test_missing_optional_engine_is_explicit(store_with_png):
    report = scan_upload(store_with_png.store, store_with_png.upload_id, ScanLimits(), which=lambda _: None)
    assert report.adapters["malware"].status == "not_installed"
    assert report.adapters["metadata"].status in {"not_installed", "not_applicable"}
```

- [ ] **Step 2: Implement scan dataclasses**

```python
@dataclass(frozen=True)
class ScanLimits:
    wall_seconds: float = 20.0
    max_output_bytes: int = 1_048_576
    max_file_bytes_for_text_probe: int = 8_388_608
    max_worker_memory_bytes: int = 1_073_741_824

@dataclass(frozen=True)
class AdapterResult:
    status: str; engine: str; version: str | None; detail: str

@dataclass(frozen=True)
class ScanReport:
    schema_version: str; upload_id: str; sha256: str; detected_type: str
    declared_extension: str; extension_consistent: bool | None
    indicators: tuple[str, ...]; adapters: dict[str, AdapterResult]
    isolation_status: str; top_level_status: str
```

- [ ] **Step 3: Implement byte/MIME identification inside worker**

Use `/usr/bin/file --brief --mime-type <blob>` via argument array if available; record engine/version. Compare declared extension via `mimetypes.guess_type` only as a hint. Re-hash blob in worker and require digest match with manifest before format-specific parsing.

- [ ] **Step 4: Add optional ClamAV/YARA adapters**

Discover exact executable with `shutil.which`. Execute inside the same sandboxed worker boundary. Record unavailable/error/indicator status; do not install software automatically.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/operator/quarantine_scan.py capt_ui/operator/quarantine_worker.py tests/capt_ui/test_quarantine_scan.py
git commit -m "feat(intake): add explicit quarantine scan pipeline"
```

---

### Task 4: Archive/container defensive inspection

**Interfaces:**
- Produces `inspect_archive(blob, derived_root, limits) -> ArchiveReport`.
- Never calls `ZipFile.extract*` or `TarFile.extract*`.

- [ ] **Step 1: Write traversal/symlink/ratio/count RED tests**

```python
def test_zip_dotdot_member_is_blocked(tmp_path):
    archive = make_zip(tmp_path, {"../../escape.txt": b"x"})
    report = inspect_archive(archive, tmp_path / "derived", ArchiveLimits())
    assert "path_traversal" in report.indicators
    assert not (tmp_path / "escape.txt").exists()


def test_archive_expansion_ratio_is_bounded(tmp_path):
    archive = make_zip(tmp_path, {"huge.txt": b"A" * 2_000_000})
    report = inspect_archive(archive, tmp_path / "derived", ArchiveLimits(max_expansion_ratio=2.0, max_total_uncompressed=1_000_000))
    assert report.blocked is True
```

- [ ] **Step 2: Implement exact limits**

`ArchiveLimits(max_depth=4, max_files=1000, max_total_uncompressed=512*1024*1024, max_single_member=128*1024*1024, max_expansion_ratio=100.0, wall_seconds=20.0)`.

Normalize with `PurePosixPath`; reject absolute paths/`..`; reject ZIP symlink mode and TAR symlink/hardlink entries. Stream each allowed child into `derived/<child-id>/blob` while enforcing counters.

- [ ] **Step 3: Recursively scan children under depth/cycle budget**

Link child scan records to parent upload/entry digest. Digest-repeat at the same ancestry path terminates recursion with an explicit cycle indicator.

- [ ] **Step 4: Run GREEN and commit**

```bash
python -m pytest tests/capt_ui/test_quarantine_archive.py -q
git add capt_ui/operator/quarantine_archive.py tests/capt_ui/test_quarantine_archive.py
git commit -m "feat(intake): bound archive inspection"
```

---

### Task 5: Image/media metadata and stego indicators

**Interfaces:**
- Produces `inspect_media(blob) -> MediaInspection` inside the scanner worker.

- [ ] **Step 1: Write RED EXIF/stego-wording tests**

```python
def test_no_metadata_does_not_claim_authenticity(sample_png_without_metadata):
    result = inspect_media(sample_png_without_metadata)
    assert result.metadata_present is False
    assert result.alteration_assessment == "cannot_determine"
    assert "No steganographic indicators detected by available checks." in result.human_summary
    assert "No steganography exists" not in result.human_summary
```

Add JPEG fixtures with ordinary EXIF/GPS and conflicting/rewritten metadata; expose fields and inconsistency indicators without claiming authenticity.

- [ ] **Step 2: Implement bounded PNG/JPEG structure parsing**

Parse PNG chunk headers/lengths/CRC boundaries and JPEG marker segments with explicit max lengths. Record dimensions, metadata presence, terminal marker/chunk, trailing bytes, thumbnail/main-image inconsistency when available, and malformed structure.

- [ ] **Step 3: Add `exiftool` adapter when installed**

Run `exiftool -json -n <blob>` inside scanner sandbox with timeout/output ceiling. Store only normalized metadata fields required by the report plus raw adapter output digest/path under `scan/`.

- [ ] **Step 4: Implement declared stego heuristics only**

V1 indicators: appended/trailing payload signatures, oversized/unusual ancillary chunks, alpha-channel presence/coverage metadata, embedded-file signatures, and optional installed format-specific scanner results. Human summary must name coverage and limitations.

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m pytest tests/capt_ui/test_quarantine_media.py -q
git add capt_ui/operator/quarantine_media.py tests/capt_ui/test_quarantine_media.py
git commit -m "feat(intake): inspect media metadata and stego indicators"
```

---

### Task 6: Explicit disposition and FileReference

**Interfaces:**
- Produces `QuarantineStore.disposition(upload_id, action) -> FileReference | None`.
- Actions exactly: `use_in_chat`, `add_to_project`, `extract_safe_content`, `inspect_deeper`, `keep_quarantined`, `delete`.

- [ ] **Step 1: Write RED scan-vs-permission tests**

```python
def test_scan_complete_is_not_context_eligible(quarantined_clean_record):
    assert quarantined_clean_record.state == "AWAITING_USER_DISPOSITION"
    assert quarantined_clean_record.allowed_uses == ()


def test_use_in_chat_creates_reference_without_copying_bytes(store, upload_id):
    ref = store.disposition(upload_id, "use_in_chat")
    assert ref.allowed_uses == ("chat_context",)
    assert store.blob_path(upload_id).exists()
```

- [ ] **Step 2: Implement `FileReference`**

Fields: `upload_id`, `original_name`, `sha256`, `byte_count`, `detected_type`, `scan_status`, `scan_digest`, `quarantine_path_ref`, `promoted_at`, `project_ids`, `allowed_uses`, `provenance`.

`BLOCKED` never grants `chat_context`, `content_extraction`, or runnable-workspace use. `SUSPICIOUS` stays visibly suspicious after explicit promotion. `INCOMPLETE_SCAN` cannot be represented as `NO_KNOWN_INDICATORS`.

- [ ] **Step 3: Implement delete/tombstone semantics**

Explicit delete removes original/derived/scan bytes. Preserve minimal tombstone: upload ID, original digest, deletion timestamp, final disposition; original filename is omitted when minimal-retention mode is active.

- [ ] **Step 4: Commit**

```bash
git add capt_ui/operator/quarantine.py tests/capt_ui/test_quarantine.py
git commit -m "feat(intake): require explicit upload disposition"
```

---

### Task 7: Operator CLI and Swift bridge

**Interfaces:**
- CLI: `capt-ui quarantine ingest <path>`, `scan <upload-id>`, `show <upload-id>`, `disposition <upload-id> <action>`, `delete <upload-id>`.
- Swift: typed `CAPTQuarantineSnapshot` / `CAPTFileReferenceSnapshot`.

- [ ] **Step 1: Add Python CLI RED tests using temporary `CAPT_STATE_DIR`**

Assert JSON output is human-projectable and source picker path never appears in any RuntimeService command payload.

- [ ] **Step 2: Add Swift decoding RED test**

```swift
@Test func decodesQuarantineSnapshot() throws {
    let data = #"{"uploadId":"upl-1","state":"AWAITING_USER_DISPOSITION","scanStatus":"NO_KNOWN_INDICATORS"}"#.data(using: .utf8)!
    let value = try JSONDecoder().decode(CAPTQuarantineSnapshot.self, from: data)
    #expect(value.uploadID == "upl-1")
    #expect(value.state == .awaitingUserDisposition)
}
```

- [ ] **Step 3: Implement CLI/Swift wrappers**

All user paths are subprocess argument elements, never shell strings. Swift calls return typed snapshots; raw scan JSON remains available for ResultPresentation later.

- [ ] **Step 4: Run focused tests and commit**

```bash
python -m pytest tests/capt_ui/test_quarantine*.py -q
cd capt_ui/surfaces/desktop_swift && swift test --filter CAPTQuarantine
git add capt_ui capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): bridge quarantine intake to native app"
```

---

### Task 8: Native Attach Files UX and no-bypass acceptance

**Interfaces:**
- Picker -> quarantine status card -> explicit disposition -> eligible `FileReference` chip.
- `CAPTChatCoordinator.requestApproval` never accepts arbitrary picker paths.

- [ ] **Step 1: Write Swift store state tests**

While `SCANNING`, text composition may continue but the pending attachment is excluded from normalized composer context. After `use_in_chat`, only the `FileReference` ID/digest becomes eligible.

- [ ] **Step 2: Implement file picker**

Use `fileImporter` or `NSOpenPanel` with regular-file selection only. Security-scoped access, when returned by macOS, lasts only through the copy into quarantine and is released immediately afterward.

- [ ] **Step 3: Render human scan/disposition card**

Default shows status, detected type, material indicators, scanner coverage, and recommended next action. Metadata/full scan/raw JSON are disclosures. Policy-disabled actions remain visible with plain-language reason.

- [ ] **Step 4: Add no-bypass integration test**

Select file and Send before scan/disposition: approval payload contains no file path/content/reference. Complete `use_in_chat`; next Send contains only stable cleared reference/digest.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add secure attachment intake UX"
```

---

### Task 9: Secure Intake subsystem gate

- [ ] **Step 1: Full Python suite alone**

```bash
python -m pytest -q
```

- [ ] **Step 2: Full Swift suite/build alone**

```bash
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```

- [ ] **Step 3: Representative fixture matrix**

Plain text; Mach-O/ELF/script; JPEG with ordinary EXIF/GPS; image without metadata; malformed image; image with trailing payload; ZIP traversal; bounded expansion-ratio fixture; symlink/FIFO source; missing sandbox primitive simulation; missing/existing optional scanners.

- [ ] **Step 4: Filesystem permission verification**

```bash
find "$CAPT_STATE_DIR/quarantine" -maxdepth 3 -type d -exec stat -f '%Lp %N' {} \;
find "$CAPT_STATE_DIR/quarantine" -maxdepth 4 -type f -exec stat -f '%Lp %N' {} \;
```

Expected directories `700`, sensitive files `600`, no execute bits.

- [ ] **Step 5: Sandbox verification**

Worker fixture attempts outbound socket connect and write outside scan/temp roots; sandboxed run must fail both operations. A normal allowed blob read + scan-dir write must succeed.

- [ ] **Step 6: RuntimeService ledger neutrality**

Record head/digest before and after ingest/scan/disposition UI work; identical. A later governed model execution referencing a cleared file advances canonical state only through the ordinary approval/admission path.
