# Secure Intake / Quarantine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Accept arbitrary regular-file uploads as hostile opaque bytes, scan them inside a bounded quarantine boundary, and require explicit user disposition before they become context-eligible.

**Architecture:** A Python Operator Plane quarantine service owns opaque storage, manifests, scan orchestration, and dispositions under `~/.capt/quarantine`. Scanner adapters execute without shell interpolation, without provider credentials, and under bounded wall-clock/output limits. Swift only selects files and renders state; it never feeds picker paths directly to a model.

**Tech Stack:** Python stdlib (`hashlib`, `json`, `mimetypes`, `pathlib`, `subprocess`, `zipfile`, `tarfile`, `stat`, `secrets`, `os`); optional installed scanners discovered explicitly; existing CAPT Artifact/Workspace containment helpers; Swift 6/SwiftUI; pytest; Swift tests.

**Spec:** `docs/superpowers/specs/2026-08-19-public-release-quarantine-projects-council-design.md` Parts I §§4-13.

## Global Constraints

- No file-extension allowlist for ordinary regular files.
- Directories/repos use Workspace selection instead of upload semantics.
- Sockets, FIFOs, devices, and other special nodes are rejected.
- Original bytes are immutable after intake and stored without execute bits.
- Scanner failure/unavailability yields uncertainty, never `clean`.
- No scanner receives provider/API credentials.
- No scanner gets network permission from CAPT.
- Archive extraction stays under `derived/` with traversal/symlink/bomb ceilings.
- Image/media metadata authenticity is never inferred from structural validity alone.
- Steganography output uses indicator/coverage language only.
- A scan result does not grant context permission.

---

## File Structure

**Create:**
- `capt_ui/operator/quarantine.py` — storage, manifest, state machine, disposition, `FileReference`.
- `capt_ui/operator/quarantine_scan.py` — bounded scanner pipeline and adapter results.
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
- current `capt-ui` CLI entrypoint to add `quarantine ingest|scan|show|disposition|delete`.
- `capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Services/CAPTOperatorCLI.swift` to invoke those commands.
- `capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Stores/CAPTOperatorStore.swift` to hold selected/scanning attachments.
- `capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/ChatView.swift` only to surface the attachment panel entry point; file logic remains outside the view.

---

### Task 1: Quarantine storage and hostile intake

**Interfaces:**
- Produces: `QuarantineStore.ingest(source: Path) -> QuarantineRecord`.
- Produces: immutable `QuarantineRecord` serialization with `uploadId`, original name, SHA-256, byte count, state, paths, timestamps.

- [ ] **Step 1: Write failing intake tests**

```python
# tests/capt_ui/test_quarantine.py
from pathlib import Path
import os
import stat
import pytest

from capt_ui.operator.quarantine import QuarantineError, QuarantineStore


def test_ingest_copies_regular_file_to_opaque_private_location(tmp_path: Path):
    src = tmp_path / "../../evil name.txt"
    src = tmp_path / "evil name.txt"
    src.write_bytes(b"CAPT upload")
    store = QuarantineStore(tmp_path / "state")

    record = store.ingest(src)

    assert record.original_name == "evil name.txt"
    assert record.state == "STORED_OPAQUE"
    assert record.sha256 == "sha256:3e7a9e7bb2115ab10cde838a0e24d80bcdaf40f29192603df50ecb34bfa16cc5"
    blob = store.blob_path(record.upload_id)
    assert blob.name == "blob"
    assert blob.read_bytes() == b"CAPT upload"
    assert stat.S_IMODE(blob.stat().st_mode) == 0o600
    assert stat.S_IMODE(blob.parent.parent.stat().st_mode) == 0o700


def test_ingest_rejects_directory(tmp_path: Path):
    store = QuarantineStore(tmp_path / "state")
    with pytest.raises(QuarantineError, match="regular file"):
        store.ingest(tmp_path)
```

- [ ] **Step 2: Run tests and confirm RED**

```bash
python -m pytest tests/capt_ui/test_quarantine.py -q
```

Expected: import/class failure.

- [ ] **Step 3: Implement minimal record/store**

```python
# capt_ui/operator/quarantine.py
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import json, os, secrets, stat, tempfile


class QuarantineError(RuntimeError):
    pass


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

    def ingest(self, source: Path, *, now: str = "1970-01-01T00:00:00Z") -> QuarantineRecord:
        source = Path(source)
        st = source.lstat()
        if not stat.S_ISREG(st.st_mode):
            raise QuarantineError("upload source must be a regular file")
        upload_id = "upl-" + secrets.token_hex(16)
        upload_root = self.root / upload_id
        original = upload_root / "original"
        original.mkdir(parents=True, mode=0o700)
        os.chmod(upload_root, 0o700)
        digest = sha256()
        byte_count = 0
        blob = original / "blob"
        with source.open("rb") as src, blob.open("xb") as dst:
            while chunk := src.read(1024 * 1024):
                digest.update(chunk); byte_count += len(chunk); dst.write(chunk)
        os.chmod(blob, 0o600)
        record = QuarantineRecord("1.0.0", upload_id, source.name, "sha256:" + digest.hexdigest(), byte_count, "STORED_OPAQUE", now)
        self._atomic_json(upload_root / "manifest.json", asdict(record))
        return record
```

Implement `_atomic_json()` with `tempfile.NamedTemporaryFile(dir=target.parent, delete=False)`, `json.dump(..., sort_keys=True)`, `os.fchmod(..., 0o600)`, `os.replace()`.

- [ ] **Step 4: Run tests GREEN and add special-node tests**

Use `os.mkfifo` where supported; assert FIFO rejection. Add a symlink source test and require rejection because `lstat()` is not regular.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/operator/quarantine.py tests/capt_ui/test_quarantine.py
git commit -m "feat(intake): add opaque quarantine storage"
```

---

### Task 2: Scanner result vocabulary and bounded common scan

**Interfaces:**
- Consumes: `QuarantineStore.blob_path(upload_id)`.
- Produces: `scan_upload(store, upload_id, limits) -> ScanReport`.
- Produces adapter states: `not_installed`, `not_applicable`, `passed_without_indicator`, `indicator_found`, `scanner_error`.

- [ ] **Step 1: Write RED tests for byte identification and missing scanners**

```python
from capt_ui.operator.quarantine_scan import ScanLimits, scan_upload


def test_scan_reports_magic_mime_and_scanner_inventory(store_with_png):
    report = scan_upload(store_with_png.store, store_with_png.upload_id, ScanLimits())
    assert report.top_level_status in {"NO_KNOWN_INDICATORS", "SUSPICIOUS", "INCOMPLETE_SCAN"}
    assert report.sha256 == store_with_png.record.sha256
    assert report.detected_type
    assert "malware" in report.adapters
    assert report.adapters["malware"].status in {
        "not_installed", "passed_without_indicator", "indicator_found", "scanner_error"
    }
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/capt_ui/test_quarantine_scan.py -q
```

- [ ] **Step 3: Implement common scan without a shell**

Define:

```python
@dataclass(frozen=True)
class ScanLimits:
    wall_seconds: float = 15.0
    max_output_bytes: int = 1_048_576
    max_file_bytes_for_text_probe: int = 8_388_608

@dataclass(frozen=True)
class AdapterResult:
    status: str
    engine: str
    version: str | None
    detail: str

@dataclass(frozen=True)
class ScanReport:
    schema_version: str
    upload_id: str
    sha256: str
    detected_type: str
    declared_extension: str
    extension_consistent: bool | None
    indicators: tuple[str, ...]
    adapters: dict[str, AdapterResult]
    top_level_status: str
```

Use `subprocess.run(["/usr/bin/file", "--brief", "--mime-type", blob], shell=False, timeout=limits.wall_seconds, capture_output=True, env={"PATH": "/usr/bin:/bin:/opt/homebrew/bin"})` when available. Never copy `os.environ` wholesale into scanner subprocesses.

For optional engines, discover exact executables with `shutil.which`: `clamscan`, `yara`, `exiftool`. If absent, record `not_installed`; never silently skip.

- [ ] **Step 4: Add timeout/error tests**

Inject a runner callable into scanner adapters so tests can simulate `subprocess.TimeoutExpired` without sleeping. Assert the result is `scanner_error` and the report cannot become a stronger status than `INCOMPLETE_SCAN` when required baseline inspection failed.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/operator/quarantine_scan.py tests/capt_ui/test_quarantine_scan.py
git commit -m "feat(intake): add bounded quarantine scan pipeline"
```

---

### Task 3: Archive/container defensive inspection

**Interfaces:**
- Produces: `inspect_archive(blob, derived_root, limits) -> ArchiveReport`.
- Never extracts using `ZipFile.extract*` or `TarFile.extract*` directly.

- [ ] **Step 1: Write traversal, symlink, ratio and count RED tests**

```python
def test_zip_dotdot_member_is_blocked(tmp_path):
    archive = make_zip(tmp_path, {"../../escape.txt": b"x"})
    report = inspect_archive(archive, tmp_path / "derived", ArchiveLimits())
    assert "path_traversal" in report.indicators
    assert not (tmp_path / "escape.txt").exists()


def test_archive_expansion_ratio_is_bounded(tmp_path):
    archive = make_zip(tmp_path, {"huge.txt": b"A" * 2_000_000})
    limits = ArchiveLimits(max_expansion_ratio=2.0, max_total_uncompressed=1_000_000)
    report = inspect_archive(archive, tmp_path / "derived", limits)
    assert report.blocked is True
```

- [ ] **Step 2: Implement normalized member validation**

Define `ArchiveLimits(max_depth=4, max_files=1000, max_total_uncompressed=512*1024*1024, max_single_member=128*1024*1024, max_expansion_ratio=100.0, wall_seconds=20.0)`.

Normalize member names with `PurePosixPath`; reject absolute paths and any `..` component. Reject ZIP Unix symlink mode via `ZipInfo.external_attr`; reject TAR symbolic/hard links. Stream allowed children manually into `derived/<child-id>/blob` with a running uncompressed-byte counter.

- [ ] **Step 3: Run archive suite GREEN**

```bash
python -m pytest tests/capt_ui/test_quarantine_archive.py -q
```

- [ ] **Step 4: Commit**

```bash
git add capt_ui/operator/quarantine_archive.py tests/capt_ui/test_quarantine_archive.py
git commit -m "feat(intake): bound archive inspection"
```

---

### Task 4: Image/media metadata and stego indicators

**Interfaces:**
- Produces: `inspect_media(blob) -> MediaInspection`.
- Reports coverage and indicators, never a universal negative.

- [ ] **Step 1: Write RED tests for EXIF present/absent and wording**

```python
def test_no_metadata_does_not_claim_authenticity(sample_png_without_metadata):
    result = inspect_media(sample_png_without_metadata)
    assert result.metadata_present is False
    assert result.alteration_assessment == "cannot_determine"
    assert "No steganographic indicators detected by available checks." in result.human_summary
    assert "No steganography exists" not in result.human_summary
```

Add a fixture JPEG containing ordinary EXIF and GPS tags; assert fields are surfaced but authenticity remains `cannot_determine` absent stronger evidence.

- [ ] **Step 2: Implement format-safe built-in checks**

Implement PNG chunk parsing and JPEG marker walking with explicit bounds. Record dimensions/header consistency, trailing bytes after terminal image markers/chunks, metadata presence, and parse errors. Run `exiftool -json -n` only when installed, using sanitized environment and timeout.

For stego indicators, implement only declared heuristics in v1: trailing payload signature scan, unusually large ancillary chunks, alpha-channel presence/coverage, and optional external adapter results. Do not label statistical absence as proof.

- [ ] **Step 3: Run media tests GREEN**

```bash
python -m pytest tests/capt_ui/test_quarantine_media.py -q
```

- [ ] **Step 4: Commit**

```bash
git add capt_ui/operator/quarantine_media.py tests/capt_ui/test_quarantine_media.py
git commit -m "feat(intake): inspect media metadata and stego indicators"
```

---

### Task 5: Explicit disposition and FileReference

**Interfaces:**
- Produces: `QuarantineStore.disposition(upload_id, action) -> FileReference | None`.
- `action` exact enum: `use_in_chat`, `add_to_project`, `extract_safe_content`, `inspect_deeper`, `keep_quarantined`, `delete`.

- [ ] **Step 1: Write RED tests proving scan != permission**

```python
def test_scan_complete_is_not_context_eligible(quarantined_clean_record):
    assert quarantined_clean_record.state == "AWAITING_USER_DISPOSITION"
    assert quarantined_clean_record.allowed_uses == ()


def test_use_in_chat_creates_reference_without_copying_bytes(store, upload_id):
    ref = store.disposition(upload_id, "use_in_chat")
    assert ref.upload_id == upload_id
    assert ref.allowed_uses == ("chat_context",)
    assert store.blob_path(upload_id).exists()
```

- [ ] **Step 2: Implement immutable disposition receipt**

`FileReference` must contain `upload_id`, `original_name`, `sha256`, `byte_count`, `detected_type`, `scan_status`, `scan_digest`, `quarantine_path_ref`, `promoted_at`, `project_ids`, `allowed_uses`, `provenance`.

High-risk/block policy: `BLOCKED` never grants `chat_context`, `content_extraction`, or runnable-workspace use. `SUSPICIOUS` requires an explicit action and remains marked suspicious in the reference.

- [ ] **Step 3: Add deletion semantics test**

Delete bytes/derived scan output after explicit `delete`, preserving only minimal tombstone fields: upload ID, original digest, deletion timestamp, final disposition. Verify no original filename retention when configured privacy mode requests minimal tombstones.

- [ ] **Step 4: Commit**

```bash
git add capt_ui/operator/quarantine.py tests/capt_ui/test_quarantine.py
git commit -m "feat(intake): require explicit upload disposition"
```

---

### Task 6: Operator CLI and Swift bridge

**Interfaces:**
- CLI JSON commands: `capt-ui quarantine ingest <path>`, `scan <upload-id>`, `show <upload-id>`, `disposition <upload-id> <action>`, `delete <upload-id>`.
- Swift produces `CAPTQuarantineSnapshot` and `CAPTFileReferenceSnapshot`.

- [ ] **Step 1: Add Python CLI RED tests**

Test machine-readable output with temporary `CAPT_STATE_DIR`; assert no source path appears in model/runtime command payloads.

- [ ] **Step 2: Add Swift model decoding RED tests**

```swift
@Test func decodesQuarantineSnapshot() throws {
    let data = #"{"uploadId":"upl-1","state":"AWAITING_USER_DISPOSITION","scanStatus":"NO_KNOWN_INDICATORS"}"#.data(using: .utf8)!
    let value = try JSONDecoder().decode(CAPTQuarantineSnapshot.self, from: data)
    #expect(value.uploadID == "upl-1")
    #expect(value.state == .awaitingUserDisposition)
}
```

- [ ] **Step 3: Implement CLI and `CAPTOperatorCLI` async wrappers**

All user-provided paths are passed as argument-array elements, never concatenated into shell strings. Return typed JSON snapshots.

- [ ] **Step 4: Run focused Python + Swift tests**

```bash
python -m pytest tests/capt_ui/test_quarantine*.py -q
cd capt_ui/surfaces/desktop_swift && swift test --filter CAPTQuarantine
```

- [ ] **Step 5: Commit**

```bash
git add capt_ui capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): bridge quarantine intake to native app"
```

---

### Task 7: Native Attach Files UX and no-bypass acceptance

**Interfaces:**
- Produces picker -> quarantine card -> disposition flow.
- Does not modify `CAPTChatCoordinator.requestApproval` to accept arbitrary file paths.

- [ ] **Step 1: Write Swift store tests for selected/scanning/disposition states**

Model the UI states explicitly; while `SCANNING`, `canComposeInActiveChat` may remain true for text, but the attachment is excluded from the outgoing context draft until a permitted disposition creates a `FileReference`.

- [ ] **Step 2: Implement file picker in `AttachmentQuarantineView`**

Use `fileImporter` or `NSOpenPanel` with regular-file selection. Do not request directory selection here. Immediately hand each URL to the quarantine bridge; release any security-scoped resource after copying into quarantine.

- [ ] **Step 3: Render scan summary and user actions**

Default card shows human summary/status; metadata/full scan details are disclosures. High-risk/blocked action buttons are disabled according to policy.

- [ ] **Step 4: Add no-bypass integration test**

Instrument a fake runtime/operator bridge. Select a file and submit a prompt before scan/disposition completes. Assert the approval request contains no picker path/file content reference. After `use_in_chat`, assert only the `FileReference` identity/digest becomes eligible input.

- [ ] **Step 5: Run acceptance**

```bash
python -m pytest tests/capt_ui/test_quarantine*.py -q
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```

- [ ] **Step 6: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add secure attachment intake UX"
```

---

### Task 8: Secure Intake subsystem gate

- [ ] **Step 1: Run full Python suite alone**

```bash
python -m pytest -q
```

- [ ] **Step 2: Run full Swift suite/build alone**

```bash
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```

- [ ] **Step 3: Manually exercise representative fixtures**

Required fixture matrix: plain text; JPEG with normal EXIF; JPEG/PNG without metadata; image with trailing payload; ZIP path traversal; ZIP expansion bomb fixture kept safely small via declared compressed/uncompressed metadata; shell script; executable Mach-O/ELF fixture; malformed image; scanner-not-installed environment.

- [ ] **Step 4: Verify filesystem permissions**

```bash
find "$CAPT_STATE_DIR/quarantine" -maxdepth 3 -type d -exec stat -f '%Lp %N' {} \;
find "$CAPT_STATE_DIR/quarantine" -maxdepth 4 -type f -exec stat -f '%Lp %N' {} \;
```

Expected: directories `700`; sensitive files `600`; no execute bits.

- [ ] **Step 5: Verify RuntimeService ledger neutrality**

Record ledger head/digest before ingest/scan/project-ineligible disposition and after. They must be identical. Then run one governed prompt using an explicitly eligible `FileReference`; only the consequential RuntimeService path may advance canonical state.
