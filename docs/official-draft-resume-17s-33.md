# VARYN 17S-33 | Explicit DPAPI-encrypted synthetic draft resume

Date: 2026-11-05. This stage adds **opt-in save/restore of five owner-authored synthetic draft fields** to the portable official-app workbench. It does **not** persist authenticated provider history, returned AI text, manual relay state, original clipboard, approvals, private documents or existing project RAM note board.

## User problem and narrow scope
Closing VARYN currently discards the workbench's in-memory editable synthetic task and note. The Windows DPAPI helper `varyn/dpapi_vault.py` was already present, but never connected to the official-app draft editor. Rather than introducing a new plaintext database or unsanctioned consumer-app integration, this milestone reuses that Windows-user-bound DPAPI envelope for **one explicitly selected NEW file**.

New buttons in the focused workbench:
- `17S-33 | Save encrypted synthetic draft (manual)`: checks exact `SYNTHETIC:` task/note, fixed official target, bounded project/topic, recognized secret patterns; shows an exact scrollable pre-save review, then asks the owner for a new `.varyn` file. Checks the live fields again after both dialogs; cannot overwrite an existing file. Uses DPAPI `write_sealed`, which writes no plaintext intermediate.
- `17S-33 | Restore encrypted draft (manual)`: requires an idle/empty relay state and empty pasted-reply editor; asks the owner to choose a `.varyn` file; decrypts and strictly validates all schema fields/flags; shows exact contents for approval. Applies **only** target, task, note, project and topic when the live editor and relay state remain unchanged through review. Note-sharing remains OFF.

No automatically scheduled save, restore, browser navigation, clipboard copy, provider request or user-account history import occurs. Restore is **not** resuming the original active relay or authenticated session: a fresh outbound clipboard handoff requires the pre-existing explicit approvals. A failed/declined restore does not replace current text.

## Security and reversibility
Schema `varyn.synthetic_official_draft.v1` permits only fixed keys and the official target allowlist. Three false flags (`provider_history_authenticated`, `automatic_bidirectional_sync`, `pasted_reply_persisted`) and `manual_only=true` are mandatory. Inputs are synthetic-only and size limited; obvious credentials are rejected but heuristic scanning is NOT a privacy guarantee.

DPAPI is tied to the Windows user's account/profile. These files are **not** portable backups across devices, cryptographically authenticated provider transcripts, a dedicated malware-resistant vault or a guarantee against local administrator compromise. Existing files are never overwritten, so owners can compare or discard old versions. Paths are chosen locally, not placed in the repo or transmitted by VARYN. Encrypted file names may still reveal owner-chosen labels to the OS.

## Test and deployment gates
- `tests/test_official_draft_resume.py`: cross-platform strict format validation, authority-flag refusals, obvious secret detection, correct DPAPI wrapper delegation and extension rejection, and native Windows encrypt/read/no-overwrite/tamper cases.
- `tests/test_official_draft_resume_tk.py`: hosted Windows actual Tk workbench widgets and DPAPI file operations with simulated owner modal decisions, denied-save/restore, approved roundtrip, pasted-reply blocking and no relay permission restoration.
- `.github/workflows/memory-checks.yml`: dedicated 17S-33 tests ahead of full suite; separate hosted Windows native Tk gate. Exact-commit Windows+Ubuntu regression and portable frozen EXE smoke/artifacts required before green.

**Gate still open:** real owner device and full real official ChatGPT/Claude/Gemini account sync. `varyn.option_c_gate` must continue to block two-way automatic consumer-app synchronization. PR #1 remains DRAFT and `main` is not merged.
