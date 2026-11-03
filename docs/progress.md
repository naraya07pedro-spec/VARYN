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
- Added six targeted synthetic tests; CI verification pending.
- Did not add semantic matching, true citations, authentication, encryption, provider calls, or model token budgets.
