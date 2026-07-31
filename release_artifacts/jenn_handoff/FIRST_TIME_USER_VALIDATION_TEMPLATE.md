# First-Time User Validation — Task Sheet & Observation Form

You are receiving CAPT Core v0.5.0 as a first-time user. This is an independent
usability and packaging test. Do NOT receive coaching before you record where
you became blocked. Your confusion is evidence.

## Artifact
- `capt_core_v0.5_external.tar.gz` (source archive) OR
- `capt_solo-0.5.0-py3-none-any.whl` (wheel) OR
- `capt_solo-0.5.0.tar.gz` (sdist)
- Checksum file: `SHA256SUMS.txt` (verify before installing)

## Tasks (record every command and result)
1. Verify the artifact checksum.
2. Identify installation prerequisites (Python version? anything else?).
3. Create a clean Python virtual environment.
4. Install CAPT from the provided material (wheel recommended):
   `pip install capt_solo-0.5.0-py3-none-any.whl`
5. Confirm the installed version: `capt --version` or `python -m capt_cli --version`.
6. Run the health command: `capt doctor`.
7. Run the first documented example (see README "Five-Minute Verification Flow"
   or `examples/verification_first/run.py` inside the source archive).
8. Locate how to verify the release (README "Verification Commands").
9. In your own words, write what CAPT is and is not.
10. Identify which features are optional, experimental, or deferred.
11. Uninstall CAPT cleanly.

## Observation form (fill in as you go)
- Operating system: ____________
- Architecture: ____________
- Python version: ____________
- Shell/terminal: ____________
- Time to successful install: ____________
- Time to first successful documented workflow: ____________
- Every command entered: ____________
- Every error encountered (verbatim): ____________
- Points of confusion: ____________
- Undocumented workarounds used: ____________
- Questions you wanted to ask: ____________
- Final success or failure: ____________
- Your unedited summary of the experience: ____________

## Rules for the observer
- Record confusion; do not self-censor.
- If you become blocked, note the exact block before seeking help.
- Do not use private/tribal knowledge not in the provided docs.
