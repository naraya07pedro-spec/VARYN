# VARYN: first implementation checkpoint

**Status:** source-code prototype committed for review. Not production-ready.

## What this checkpoint implements
- A dependency-free Python / SQLite local memory experiment.
- Store, retrieve, and delete user-labeled notes across process restarts.
- Filter retrieval by project and owner label.
- Small automated tests for persistence, owner-scoping, deletion, project filtering, and literal search.
- Git ignore rules to prevent accidental routine commits of local database files and common secrets.

## Second checkpoint: consistent SQLite backups
- Added `varyn/backup.py` using SQLite's official online backup interface.
- Existing backup destinations are never overwritten; new snapshots are checked with `PRAGMA quick_check`.
- Four backup tests passed in a local Python environment on 3 November 2026; GitHub Actions and Windows-specific execution remain to be verified.
- Backups are **unencrypted** and currently intended for synthetic data only. Backups on the same physical disk do not protect against hardware loss.

## Third checkpoint: fail-closed restore (3 November 2026)
- Added `varyn/restore.py`: validates the SQLite database and VARYN memory table before copying.
- Restores to a **new destination only**; existing files are never overwritten, including concurrent creation.
- Added 6 tests covering round-trip data, invalid source, corruption, conflicting destination, missing paths, and owner-label scoping.
- Verification: [GitHub Actions #41597987846](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41597987846) passed 14 tests and CLI smoke on both Ubuntu and Windows at code commit `72871996734c18f4d1bfb2c448a7bede89a309a9`.
- Owner-device acceptance, true authentication, encryption, and off-device disaster recovery are **not** implemented. Tests passed on a hosted Windows runner, not yet the owner's PC.

## Fourth checkpoint: revisioned decisions (3 November 2026)
- Added a separate SQLite decision journal with mandatory source labels and preserved history.
- Latest revision is selected explicitly; stale revision writes are rejected transactionally.
- Seven synthetic tests added. [GitHub Actions #41601099846](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41601099846) passed 21 total unit tests plus CLI smoke checks on Windows and Ubuntu.
- Provenance is **recorded, not independently verified**, and no user identity/authentication exists.

## Fifth checkpoint: bounded context retrieval
- Context builder `varyn/context.py` creates a JSON package limited by serialized character count.
- Retrieves keyword-matched memory and latest decision revisions for a specified project and caller-supplied owner label.
- Eight synthetic retrieval tests added. [GitHub Actions #41603654276](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41603654276) passed 29 total tests plus CLI checks on Windows and Ubuntu.
- This is **not semantic retrieval or LLM token counting**; no model connection or secure identity exists.

## Crucial limitations
- `--owner` is a user-provided label, **not authentication**. Any person with database access can impersonate another label. This is a logical scoping prototype, not security isolation.
- No encryption at rest, verified provenance, semantic search, token budgeting, semantic conflict resolution, provider login, model calls, agents, or user interface yet.
- Tests and CI are provided; checkpoint-specific results must be checked against the latest commit before any completion claim.
- Do not store secrets, actual private user conversations, or customer data in this experimental database.

## Local smoke test
Run from repository root using Python 3.10+:

```sh
python -m unittest discover -s tests -v
python -m varyn.memory --db demo.sqlite3 --owner demo add --project VARYN --content "First verified note"
python -m varyn.memory --db demo.sqlite3 --owner demo search --query "verified"
```

## Next gate
Verify the restore tests in CI, then test real Windows filesystem behavior and add provenance/versioned context using synthetic data. Provider access and multi-agent work remain deferred.

## Checkpoint 06: context quality (3 November 2026)
- Added suppression of whitespace/case-equivalent repeated notes without combining distinct decision keys.
- Added explicit retrieval status to distinguish no lexical match from budget-excluded evidence.
- Added six targeted synthetic tests. [GitHub Actions #41604448473](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41604448473) passed 35 total unit tests plus CLI smoke checks on Windows and Ubuntu.
- Did not add semantic matching, true citations, authentication, encryption, provider calls, or model token budgets.

## Checkpoint 07: retrieval evaluation
- Six labeled synthetic scenarios with explicit successes, misses and denominators.
- Expected baseline: 2/5 positive hits, 1/1 negative correctly rejected; benchmark intentionally exposes three known misses.
- Eight tests added. [CI #41607148369](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41607148369) passed on Windows and Ubuntu. Not representative of real user queries.

## Checkpoint 08: bilingual lexical pilot (3 November 2026)
- Added a narrow bilingual glossary, preserving all prior owner/project scoping and character budgeting.
- On the existing synthetic benchmark the expected positive hit rate is 3/5, compared with 2/5 before the change. [GitHub Actions #41611678899](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41611678899) passed 49 unit tests plus CLI smoke checks on Windows and Ubuntu.
- Added six independent glossary tests, including false-positive and isolation checks.
- This is not general multilingual semantic search and does not establish real-world quality.

## Checkpoint 09: SQLite FTS5 indexing
- On-disk FTS5 virtual table and triggers now support historical recall outside the latest write window, plus automatic updates and one-time backfill.
- Nine synthetic index tests added. Benchmark expectation on existing hand-labeled fixtures: 4/5 positive hits, 1/1 negative correctly rejected. [GitHub Actions #41612795744](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41612795744) passed on both Windows and Ubuntu.
- Indexing requires FTS5 support and additional on-disk space. First-use migration and performance on the owner's Windows laptop remain unverified.

## Checkpoint 10: Synthetic performance and memory benchmark (3 November 2026)
- Added a bounded benchmark for indexing and query latency, on-disk SQLite main file size, and Python-only peak tracked allocations.
- Added four instrumentation tests; scheduled a 300-note, five-query benchmark on CI for both Windows and Ubuntu. [GitHub Actions #41614154173](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41614154173) passed 62 unit tests and benchmark/CLI steps on Windows and Ubuntu.
- These metrics do not measure total native SQLite memory, full process RSS, or the actual owner's Windows laptop.

### Verified checkpoint 10 runner observations
- Ubuntu: index build 4.334 ms; median query 4.492 ms.
- Windows: index build 94.605 ms; median query 7.184 ms.
- Both: 300 synthetic notes, five query repetitions; database main file 114,688 bytes after indexing.
- Python-traced query peaks: 25,699 bytes (Ubuntu), 26,476 bytes (Windows). **Not total RAM or native SQLite allocations.** See chronological progress log for full measurement table and methodology.

## Checkpoint 11A: secret write guard (3 November 2026)
- Added deterministic credential-pattern refusal to memory and decision writes, using a generic error message.
- Six synthetic tests passed along with prior tests in GitHub Actions run #41614839681 on Windows and Ubuntu (68 tests total per OS).
- **Not encryption, authentication, comprehensive secret detection, or historical data cleanup.** Do not store actual credentials or private conversations.

## Checkpoint 11B: Read-only storage exposure audit
- Added diagnostics for unsafe/missing/symlink file paths and POSIX permission bits.
- Windows ACL security is intentionally reported as **unknown/uninspected**.
- Audits always return `ready_for_sensitive_data=false` because encryption and authentication are still absent.
- Eight tests added; [GitHub Actions #41616816340](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41616816340) passed **76 tests per OS** on Ubuntu and Windows, plus benchmark/CLI checks. Audit does not modify files or grant authorization.

## Checkpoint 11C-1: Windows DPAPI sealed-file experiment
- Added separate Windows-current-user DPAPI envelope for standalone byte blobs, with no-overwrite encrypted file publication.
- Eight synthetic tests added. [GitHub Actions #41621003228](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41621003228) succeeded on Windows and Ubuntu; native DPAPI tests passed on Windows and were skipped on Ubuntu as intended. 84 tests discovered per OS.
- **This does not encrypt the SQLite memory database or its backups and does not implement application authentication.** Windows account binding affects recovery/portability and does not prevent access from an already-compromised Windows session.

## Checkpoint 11C-2: Opt-in encrypted SQLite image
- New Windows-only in-memory SQLite store can save all its contents and FTS index as a DPAPI-encrypted immutable snapshot; no plaintext SQLite file is intentionally written.
- Does not touch or automatically migrate the legacy plaintext store, backup, restore, or decision journal. Explicit saves, limited to 1 MiB before encryption.
- Ten additional test methods; [GitHub Actions #41623353748](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41623353748) passed with 94 discovered tests on each of Windows and Ubuntu, with native-only tests skipped on Ubuntu. Not ready for private/secret data, Windows profile recovery, or production usage.

## Checkpoint 11C-3: Encrypted context and decision journal
- One in-memory SQLite connection is now shared by encrypted-session memory, revisioned decisions, and the existing context retrieval engine.
- Explicit DPAPI snapshot persists notes, decisions, history and FTS5 index together, with source labels still unverified.
- Added 10 targeted tests, including use-after-close, owner/project scoping and immutable revisions. [GitHub Actions #41624859520](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41624859520) passed 104 discovered tests per OS, including Windows-native DPAPI integration tests (skipped on Ubuntu by design).
- This does not migrate or secure the older plaintext database, provide identity authentication, or enable key recovery.

## Checkpoint 11D-1: Password-encrypted portable recovery (prototype)
- Added optional `cryptography` dependency for vetted scrypt + AES-256-GCM portable SQLite image recovery.
- Windows encrypted session can export a separate NEW recovery file and reopen it into RAM using a passphrase independent of its old DPAPI account.
- 13 synthetic regression methods added. [GitHub Actions #41626491782](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41626491782) passed 117 discovered tests on Windows and Ubuntu; Windows-native integration passed on Windows.
- Backup placement, passphrase strength/custody, device-migration acceptance, app authentication and secure data migration remain unverified. Still not ready for sensitive data.

## Checkpoint 11D-2: Recovery verification and unsaved-change guard
- Added read-only-in-memory portable recovery verifier: authenticated decrypt, SQLite integrity, minimum schema, owner-label consistency and metadata-only counts.
- Added opt-in `has_unsaved_changes` and `close_checked()` to help avoid silently discarding API-level writes on normal closure.
- Twelve additional tests (seven cross-platform recovery inspection, five Windows-only dirty-state). [GitHub Actions #41627317120](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41627317120) passed 129 discovered tests per OS and benchmark/CLI checks; Windows-only cases passed natively.
- Not automatic autosave, OS-level process-crash protection, FTS deep validation, secure identity, or verified real-device disaster recovery.

## Checkpoint 11D-3: Encrypted checkpoint-on-write (opt-in)
- A Windows sealed-memory session may now create a NEW DPAPI-encrypted snapshot immediately after each API-level memory or decision write using `checkpoint_dir`. The last successful snapshot is exposed as `last_checkpoint`.
- A failed checkpoint does not overwrite the previous snapshot; it raises and leaves the in-RAM write pending/dirty. Six new Windows-only tests. [GitHub Actions #41630117495](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41630117495) passed 135 discovered tests per OS; native checkpoint tests passed on Windows and were skipped on Ubuntu by design.
- Risk: full-image encryption on every write increases disk use, CPU and I/O; no retention policy, actual power-loss qualification or process-crash guarantee. Default behavior remains manual save.
