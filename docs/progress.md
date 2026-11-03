# VARYN: first implementation checkpoint

**Status:** source-code prototype committed for review. Not production-ready.

## What this checkpoint implements
- A dependency-free Python / SQLite local memory experiment.
- Store, retrieve, and delete user-labeled notes across process restarts.
- Filter retrieval by project and owner label.
- Small automated tests for persistence, owner-scoping, deletion, project filtering, and literal search.
- Git ignore rules to prevent accidental routine commits of local database files and common secrets.

## Crucial limitations
- `--owner` is a user-provided label, **not authentication**. Any person with database access can impersonate another label. This is a logical scoping prototype, not security isolation.
- No encryption at rest, provenance tracking, semantic search, token budgeting, conflict resolution, provider login, model calls, agents, or user interface yet.
- Tests are included but **not yet independently verified as passing**. A real test run and CI must precede any completion claim.
- Do not store secrets, actual private user conversations, or customer data in this experimental database.

## Local smoke test
Run from repository root using Python 3.10+:

```sh
python -m unittest discover -s tests -v
python -m varyn.memory --db demo.sqlite3 --owner demo add --project VARYN --content "First verified note"
python -m varyn.memory --db demo.sqlite3 --owner demo search --query "verified"
```

## Next gate
Verify tests, then add non-sensitive synthetic memory records, export/backup testing, and provenance, before attempting real provider integrations.
