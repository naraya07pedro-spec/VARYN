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

### Checkpoint 11B: Read-only storage exposure audit

```powershell
python -m varyn.storage_audit --db "D:\\VARYN\\data\\memory.sqlite3"
```

The command returns diagnostic JSON **without exposing local path or contents**. It rejects missing files and symbolic-link file paths. On POSIX systems it checks whether group/other bits allow access. On Windows it reports that Windows ACLs **have not been inspected**, because POSIX mode bits cannot establish Windows file security. It never repairs permissions or enables access.

**The audit always reports `ready_for_sensitive_data=false`.** Encryption, trusted identity, comprehensive ACL auditing, and backup protection are still unfinished. Neither a successful test nor a clean file-mode check makes this prototype suitable for private data.

### Checkpoint 11C-1: Experimental Windows DPAPI envelope

A separate Python module, `varyn.dpapi_vault`, can seal and unseal small **synthetic standalone byte blobs** under the logged-in Windows user's DPAPI context. It writes a newly encrypted file without replacing existing files and refuses tampered envelopes. There are no external dependencies.

```python
from varyn.dpapi_vault import write_sealed, read_sealed
write_sealed("demo.sealed", b"synthetic only")
assert read_sealed("demo.sealed") == b"synthetic only"
```

**Not a security-ready memory store:** it does **not** encrypt the existing SQLite memory tables, context index, backup/restore files or decision journal. It is NOT application-level authentication and does not protect data from someone who can run code as the unlocked Windows account. DPAPI keys may not transfer across machines/user profiles; recovery must be designed and tested. Do not put real secrets, personal chat histories or client data into the prototype.

### Checkpoint 11C-2: Experimental in-memory SQLite with encrypted snapshots

```python
from varyn.sealed_memory import SealedMemorySession

# Windows only, synthetic records only. Explicit save to a new file.
with SealedMemorySession() as memory:
    memory.add("VARYN", "synthetic storage decision")
    memory.save_new("first-snapshot.varyn")

with SealedMemorySession("first-snapshot.varyn") as memory:
    print(memory.search("storage", project="VARYN"))
```

Unlike the legacy SQLite-on-disk module, this **separate opt-in prototype** operates on an in-memory SQLite database with its FTS index and encrypts the *whole serialized image* with Windows DPAPI before publishing a new file. It never silently migrates or overwrites legacy data.

**Important limitations:** saves are manual, DPAPI sealed plaintext is limited to 1 MiB, and a lost Windows profile or device may make files unrecoverable. Windows DPAPI does not protect plaintext in memory from the logged-in Windows user or compromised processes. No app login, cross-device key recovery, multi-user access, normal context/decision integration or protected export exists. Do not store real credentials or private chat records yet.

### Checkpoint 11C-3: Encrypted decision history and context

Windows-only opt-in example, synthetic data:

```python
from varyn.sealed_memory import SealedMemorySession

with SealedMemorySession() as varyn:
    varyn.add("VARYN", "storage index kept in memory")
    varyn.put_decision("VARYN", "location", "storage on drive D", "fixture:example")
    print(varyn.context("VARYN", "storage", max_chars=4000))
    varyn.save_new("snapshot-01.varyn")

with SealedMemorySession("snapshot-01.varyn") as varyn:
    print(varyn.current_decision("VARYN", "location"))
```

The session uses one in-memory SQLite database for memory, FTS5 search and revisioned decisions. The *entire image* is serialized and encrypted by Windows DPAPI for explicit new-file snapshots; no legacy plaintext DB is migrated. Context values remain **untrusted data** and source labels are not independently verified. Snapshots require the original Windows DPAPI user context, and a lost user profile may make them unrecoverable. This does not implement application authentication, automatic save, key recovery, or private-data readiness.

### Checkpoint 11D-1: Portable recovery (optional audited dependency)

Install optional dependency from repository root:

```powershell
python -m pip install -r requirements-recovery.txt
```

Create two **separate**, encrypted files using synthetic test data on Windows:

```python
from varyn.sealed_memory import SealedMemorySession

phrase = "a long unique sample recovery phrase 2026"  # DEMO ONLY
with SealedMemorySession() as session:
    session.add("VARYN", "storage synthetic history")
    session.put_decision("VARYN", "location", "storage on drive D", "fixture:demo")
    session.save_new("windows-only.varyn")  # DPAPI current-user snapshot
    session.export_recovery("portable.varyn-recovery", phrase)  # independent recovery file

with SealedMemorySession(
    recovery_source="portable.varyn-recovery", recovery_passphrase=phrase
) as recovered:
    print(recovered.context("VARYN", "storage"))
    recovered.save_new("restored-windows.varyn")  # NEW DPAPI-protected file
```

Portable exports use scrypt and AES-256-GCM via the audited `cryptography` library, and can be decrypted on another supported OS with the correct passphrase. Never embed a **real** recovery phrase in source, command-line arguments, terminal history or logs; use a trusted passphrase manager and keep an off-device copy. Losing the phrase means the portable file cannot be recovered. Attackers with the encrypted file can attempt offline password guessing, so the minimum length requirement is not enough: use a high-entropy phrase. The KDF uses roughly 32 MiB of working memory. **This is not automatic backup, production authentication, verified cross-device migration, or a replacement for the old unencrypted database.** Snapshot size remains 1 MiB. Only synthetic data.
