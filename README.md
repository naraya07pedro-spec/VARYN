# VARYN

**An open-source personal AI workspace for shared memory, multi-model collaboration, and reliable agent workflows.**

> **Early prototype.** The only implemented component so far is a local memory experiment. No GPT, Claude, Gemini, provider authentication, model routing, agent orchestration, or full user interface is implemented.

## First development checkpoint: local memory

The prototype uses Python's standard library and an on-device SQLite file to add, search, and delete memories, labeled by project and a local owner string.

### Run with Python 3.10+

```bash
python -m unittest discover -s tests -v
python -m varyn.memory --db demo.sqlite3 --owner demo add --project VARYN --content "Remember this decision"
python -m varyn.memory --db demo.sqlite3 --owner demo search --query "decision"
python -m varyn.memory --db demo.sqlite3 --owner demo delete --id 1
```

### Local memory backup (unencrypted)

Create a non-overwriting, internally consistent SQLite snapshot:

```powershell
python -m varyn.backup --db "D:\\VARYN\\data\\memory.sqlite3" --output "D:\\VARYN\\backups\\memory-2026-11-03.sqlite3"
```

Both the source database and destination folder must already exist. This backup contains the same sensitive content as the database and **is not encrypted**; do not publish it or sync it to public storage. A backup on the same physical SSD protects against some software accidents, **not** SSD failure. Restore and Windows-specific behavior still need acceptance tests.

### Restore a backup safely (new database only)

```powershell
python -m varyn.restore --backup "D:\\VARYN\\backups\\memory-2026-11-03.sqlite3" --output "D:\\VARYN\\data\\recovered.sqlite3"
```

The restore operation validates SQLite integrity and the expected memory schema, then writes a **new** database. It refuses to overwrite an existing path. Restore is not a live database replacement and does not authenticate users. This is an unencrypted local experiment; use synthetic data only. Backup and restore across different Windows filesystems or removable drives are not yet acceptance-tested.

**Safety:** The `--owner` value is NOT authentication. Anyone with database access can read records or impersonate another owner. Do not store real secrets, personal conversations, or customer information until identity verification, authorization and data protection have been implemented and tested.

See [development evidence and limitations](docs/progress.md). Automated tests are provided and GitHub Actions is configured; do not assume they pass until CI reports results.

## Product goals, not implemented features

- Independent memory and context shared across supported AI providers.
- Explicit permission boundaries and separate owner/user workspaces.
- Official provider integrations subject to eligibility, terms and quota.
- A genuinely useful personal workspace, built incrementally without unapproved API spending.

VARYN is a distinct project from [RepoPilot AI](https://github.com/naraya07pedro-spec/repopilot-ai), which focuses on bounded issue-to-PR engineering work.

**No production-readiness or full multi-model support is claimed.**
