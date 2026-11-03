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

### Experimental revisioned decision journal (Checkpoint 04)

The separate `varyn.decisions.DecisionJournal` prototype records a **source reference** on each decision and retains all previous revisions. A caller must provide the last seen revision when updating a decision, so stale writes are rejected rather than silently replacing new instructions.

```python
from varyn.decisions import DecisionJournal
journal = DecisionJournal("demo.sqlite3", "demo")
v1 = journal.put("VARYN", "storage", "Store memory on D:", "decision:001")
v2 = journal.put("VARYN", "storage", "Keep backups off-device", "decision:002", expected_revision=v1)
print(journal.current("VARYN", "storage"))
print(journal.history("VARYN", "storage"))
journal.close()
```

**Not yet implemented:** trustworthy source authentication, conflict resolution, semantic retrieval, automated context assembly, secure identity, and encryption. A source reference is an unverified string entered by a caller, not proof that the source exists.

### Bounded context retrieval experiment (Checkpoint 05)

```powershell
python -m varyn.context --db demo.sqlite3 --owner demo --project VARYN --query "storage" --max-chars 4000
```

This prints a JSON package with lexical matches from the local memory store and **latest** matching decision revisions only. It enforces a character cap on the serialized JSON, **not** an LLM token budget. Only a recent candidate pool is searched; synonyms may not match. Every retrieved content field must be treated as untrusted data by any future model adapter. No model invocation occurs.

### Context quality and missing-evidence diagnostics (Checkpoint 06)
- Duplicate raw notes that differ only by case/spacing are suppressed; a current decision with the same text is preferred over a raw note.
- Retrieval reports `matched`, `no_match_in_sample`, or `matches_exceeded_budget`.
- **A no-match status does not mean the information is false or absent**: retrieval scans only a bounded pool and uses lexical matching.
- The package remains bounded by serialized characters, not provider model tokens.

### Checkpoint 08: Minimal bilingual glossary

The keyword retriever now understands a very small, explicitly reviewed glossary, including `penyimpanan/storage`, `memori/memory`, and `cadangan/backup`. There is no background model or embedding download.

Use `python -m varyn.evaluation` to reproduce the six-case synthetic benchmark. Its positive hit rate is expected to move from 40% to 60% on these fixed synthetic fixtures. That is **not** a valid real-world accuracy claim; the older-record and budget-related misses still remain.

### Checkpoint 09: SQLite FTS5 historical indexing

An on-disk SQLite FTS5 index now retrieves matching older notes even if many unrelated notes were added later. Existing local databases are backfilled the first time the index is initialized; triggers maintain the index for new, changed, and deleted notes. Queries are built from quoted and parameterized lexical terms with the tiny bilingual glossary.

**Operational warning:** first-time index creation can use CPU and disk space proportional to the notes stored. It needs a Python SQLite build with FTS5 and enough free disk space. No laptop-specific speed or RAM claim is made. If the index isn't available, retrieval raises an error rather than silently pretending it scanned all history.

Run the existing synthetic evaluation using `python -m varyn.evaluation`. The small fixed benchmark expects 4/5 positive hits; the oversized-record case still fails. This is not a field accuracy measurement.

### Checkpoint 10: Synthetic performance benchmark

Run a bounded local benchmark with non-sensitive generated data:

```powershell
python -m varyn.performance --rows 300 --repeats 5
```

The tool reports first-index-build timing, min/median/max context query timing, SQLite **main database file** byte counts, and Python-tracked peak allocations via `tracemalloc`. It is intentionally informational: no arbitrary speed promise, third-party package, model download, or API bill. **Tracemalloc excludes native SQLite allocations and process RSS**, and GitHub's runner is not a substitute for an acceptance test on the owner's PC. First use of FTS5 can still temporarily require meaningful CPU/disk resources.

### Checkpoint 11A: Heuristic credential write guard

VARYN refuses some **recognizable** secrets (such as common API-key/token syntax and private-key headers) before a new memory or decision revision is saved. Errors never repeat the rejected input. This uses only the Python standard library.

**Important:** pattern matching is fallible. It does not protect an existing database, encrypt data, prevent reading another owner's records, or detect every credential. Backup files are still unencrypted. Real sensitive conversations, API keys and client data must **not** be stored in this prototype. This is an incremental guard, **not proof that VARYN is secure**.
