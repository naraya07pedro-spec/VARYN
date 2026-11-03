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
- Verification is pending for this checkpoint until the new GitHub Actions run completes.
- Windows/filesystem-specific acceptance, true authentication, encryption, and off-device disaster recovery are **not** implemented.

## Crucial limitations
- `--owner` is a user-provided label, **not authentication**. Any person with database access can impersonate another label. This is a logical scoping prototype, not security isolation.
- No encryption at rest, provenance tracking, semantic search, token budgeting, conflict resolution, provider login, model calls, agents, or user interface yet.
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
