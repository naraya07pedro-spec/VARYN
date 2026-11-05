# 17S-34 | Actual frozen portable EXE restart acceptance, synthetic DPAPI only

**Date:** 2026-11-05. Existing branch PR #1 remains DRAFT; `main` is never touched by this checkpoint.

## Why this stage matters
17S-33 proved source-level DPAPI roundtrips and Tk owner-button wiring on a GitHub-hosted Windows runner, but the bundled `VARYN-Portable.exe` was only exercised by a **GUI construction/teardown smoke**. The deployed EXE might have lacked runtime dependencies for the DPAPI draft feature even though Python unit tests were green.

17S-34 adds an explicit **cross-process frozen-artifact acceptance** using the real PyInstaller executable built on the exact commit. The CI orchestration (Python on the build runner, **not required on the owner's PC**) creates one short-lived `varyn-probe-...` directory directly beneath the OS temp directory, invokes `VARYN-Portable.exe` four times with a restricted synthetic-draft test-only mode, and then destroys the test directory:
1. **Process A:** encrypt a fixed `SYNTHETIC:` task/note into a new DPAPI `synthetic-draft.varyn` file.
2. **Process B:** completely new EXE process decrypts and compares every fixed field; test orchestrator also checks no literal task/note/JSON appears in ciphertext.
3. **Process C:** another EXE process must refuse to overwrite the existing file. The original ciphertext must remain identical.
4. **Process D:** orchestrator flips one ciphertext byte; a fresh EXE process must reject the corrupted DPAPI file. A successful return is a release-blocking failure.

The probe has no free-text or user-provided payload, browser navigation, clipboard, account credential, network request or production file-access allowance. Its only directory parameter must point directly at a specifically named existing temp folder. `--smoke-directory` and `--synthetic-draft-smoke` must be supplied together; without them the normal portable application remains unchanged. `--smoke-only` GUI construction mode remains separate.

## Security and proof limits
This is **software process restart on a GitHub-hosted Windows runner**, not a recorded human owner click, and not true hardware acceptance on the owner's PC. Tests cannot independently prove all model or consumer-app access. The only data restored are five synthetic draft editor fields, not relay grants, provider replies, browser sessions, consumer-app memories or automatic ChatGPT/Claude/Gemini synchronization. DPAPI remains bound to the Windows user profile. Antivirus trust and signing are untouched.

The test-only frozen phase is intentionally never invoked during normal GUI startup. The directory check must reject unrecognized names, nonexistent directories, symlinks and escaping/nested paths; no test command may copy private files or access an official app.

## Evidence and gates
- `varyn/frozen_draft_probe.py`: fixed fixture + directory confinement + four-process acceptance logic.
- `varyn/portable_entry.py`: restricted test-only CLI phase before any Tk window is created.
- `tests/test_frozen_draft_probe.py`: cross-platform gate, Windows DPAPI source-phase negative tests.
- `.github/workflows/memory-checks.yml`: dedicated tests in both OSes and **mandatory frozen EXE restart smoke** after frozen GUI smoke but before post-run hash manifest verification or artifact publishing.
- Real owner-PC save/exit/reopen/restore acceptance still **PENDING**. Full official-app bidirectional native consumer memory sync remains **BLOCKED**.

**Status at commit creation:** implementation is staged; verify exact final HEAD Windows+Ubuntu CI, 4-process frozen restart, and same-commit artifact before marking green. Do not confuse source tests or this CI with real signed-in browser usage.
