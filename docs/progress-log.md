# VARYN development progress log

Entries describe committed changes and verification separately. This is a history, **not** a claim of production readiness.

## 2026-11-03 — Checkpoint 01: Local memory
- **Implemented:** SQLite persistence, add/search/delete, owner-label and project filtering, and unit tests.
- **Evidence:** [PR #1](https://github.com/naraya07pedro-spec/VARYN/pull/1).
- **Known risks:** owner labels are not authentication; search is literal and not semantic.

## 2026-11-03 — Checkpoint 02: Backup
- **Implemented:** SQLite online backup to a non-overwriting, new file; quick integrity validation.
- **Evidence:** [PR #1](https://github.com/naraya07pedro-spec/VARYN/pull/1); CI for combined memory/backup stage previously passed.
- **Known risks:** unencrypted snapshots; same-SSD backup is not disaster recovery; Windows-specific behavior untested.

## 2026-11-03 — Checkpoint 03: Restore
- **Implemented:** backup restore only to a fresh destination, SQLite integrity and memory schema validation, no-overwrite publication.
- **Tests added:** six targeted restore tests.
- **Verification:** [GitHub Actions run #41597987846](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41597987846): 14 tests and backup/restore CLI smoke succeeded on both Ubuntu and Windows. Tests use synthetic data.
- **Known risks:** neither authentication nor encryption; Windows validation and restoration in a real owner workflow are pending.

## 2026-11-03 — Cross-platform failure and repair
- **Initial failure:** Windows rejected deletion of temporary SQLite files while connections were still open; Linux checks had succeeded.
- **First repair:** explicitly close backup/restore connections. Windows still failed because test fixtures themselves left SQLite connections open.
- **Second repair:** close test fixture connections and commit their writes explicitly.
- **Result:** Ubuntu and Windows passed at code commit `72871996734c18f4d1bfb2c448a7bede89a309a9` via [workflow #41597987846](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41597987846).
- **Boundary:** GitHub-hosted Windows tests do not prove performance, encryption, or end-to-end operation on the owner's specific PC.

## Deferred to later stages
- Provider authentication/model routing and quota policy.
- Multi-agent orchestration, computer use, isolation/sandbox, rich UI.
- Real user data until secure identity, storage protection, and backup recovery gates are verified.

## 2026-11-03 — Checkpoint 04: Decision provenance and revisions
- **Implemented:** `varyn/decisions.py`, an append-only experimental decision journal separate from legacy memory records.
- **Behavior:** requires a nonempty source reference, retains revision history, exposes latest revision per key, and rejects writes based on outdated expected revisions inside an immediate SQLite transaction.
- **Tests added:** seven synthetic unit tests for persistence, isolation, required sources, revision history, list-current, and stale-write rejection.
- **Verification:** [GitHub Actions #41601099846](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41601099846) passed on **Windows and Ubuntu**, covering **21 unit tests** (14 existing + 7 new), plus memory/backup/restore CLI smoke checks, at code commit `f1d8536c513a388db30c4faf1715e8308623ca8b`.
- **Limitations:** source references are user-provided labels (not verifiable citations); owner labels are not authentication. No semantic retrieval or automated inference of which source is correct.
