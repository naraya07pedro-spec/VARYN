# Checkpoint 17M: Desktop unified local memory foundation

**Date:** 2026-11-04. **Branch:** feat/local-memory-prototype-20261103; draft PR #1. **Mode:** explicit, synthetic-only, local SQLite prototype.

## Implemented

- Introduced `varyn/desktop_memory.py`: opt-in local persistence layer using the existing `MemoryStore` in `varyn/memory.py`. Requires a deliberate local `--memory-db` path; without that flag no memory database is opened and all three desktop memory buttons remain disabled. No default scanning of home folders, browsers, files or conversations.
- Added **Local project**, **Save synthetic note**, **Search project notes**, and **Delete note ID** controls to `varyn/desktop.py`. Saving requires a user-initiated button press and an explicit confirmation dialog, with no automatic capture of chat transcripts. Searching requires an exact project and typed 1..100-character query; it returns at most 10 notes and shows results only locally in the UI. Deletion requires an exact project, numeric ID, and a separate explicit approval.
- Project names are a restricted 1..40-character alphanumeric/underscore/hyphen identifier starting with a letter. Every read is bound to the EXACT selected project; the underlying MemoryStore deletion accepts an optional exact project and performs owner/project/id filtering **atomically in SQLite**. The owner label is NOT authentication and should never be construed as a security boundary.
- **Safety constraint: synthetic-only.** This prototype database is unencrypted. The UI refuses notes not starting with `SYNTHETIC:`, caps note length at 1000 characters, and states plainly that real private information must not be stored. The prefix is not a guarantee that text is genuinely synthetic: users must keep it fictional. This is an **explicit development restriction**, not a full privacy/security solution.
- Memory is never silently injected into `DesktopController.send`, the 17K/17L collaboration pipeline, tool requests, network payloads, or provider APIs. The existing context-sharing checkbox still does not load memory. No automatic cross-provider synchronization or consumer ChatGPT/Claude/Gemini history read/write was implemented.
- SQLite storage survives application restarts. In-memory chat transcripts and API usage budgets continue to reset on restart. Explicit deletion does not remove earlier backups or guarantee secure erasure of unallocated SQLite blocks.
- Existing source-only Windows ZIP packaging picks up the new Python module via `varyn/*.py`; the SQLite database is NEVER included in the source ZIP.

## Safe manual verification (synthetic only)

On a Windows non-Administrator Python 3 environment, start VARYN with an explicit, dedicated empty database path whose **parent directory already exists**:

```powershell
py -3 -m varyn.desktop --memory-db ".\varyn-synthetic-notes.sqlite3"
```

Type `SYNTHETIC: checkpoint alpha` into the Message box. Set project `VARYN`, click **Save synthetic note**, and approve the dialog. The transcript will show a local ID, not the saved content. Replace the Message text with `alpha`, click **Search project notes**, and see the local result. Set project `OTHER` and repeat the search: no result should appear. To delete, select `VARYN`, replace Message text with the numeric ID shown in the transcript, click **Delete note ID**, and confirm. Restart with the same `--memory-db` to verify persistence of any nondeleted records.

Do not enter real credentials, medical records, employer data, sensitive conversations or personal files. This is a synthetic-memory development checkpoint, not ready for storing actual private memory.

## Evidence scope and next step

- New `tests/test_desktop_memory.py`: 12 independent tests for explicit save, database reopening, project isolation, atomic scoped delete, denial, literal SQL LIKE escaping, invalid IDs, closed handles, oversized content, no provider access, missing destination parents and safe symlink rejection where host permits.
- New `tests/test_desktop_memory_tk.py`: 2 Windows-only real Tk programmatic button tests for disabled-without-opt-in and synthetic save/search/delete including cross-project rejection. They do not constitute human acceptance.
- CI executes both new suites alongside the existing system regressions on Windows/Ubuntu (Windows-only Tk tests skipped on Ubuntu).
- **17N objective:** Controlled retrieval of a few cited project-scoped synthetic memory records into the multi-model collaboration plan, with explicit human approval of exactly which records reach each external provider, and measured non-contamination across projects. No automatic context upload.
- **Option C:** Automatic two-way sync inside the official consumer apps remains blocked pending verified provider read/write access. This memory feature is not a substitute for it.
