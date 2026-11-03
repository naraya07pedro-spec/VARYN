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

## 2026-11-03 — Checkpoint 05: Bounded context retrieval
- **Implemented:** `varyn/context.py` selects memory notes and the latest decision revision with lexical relevance scores, strictly filtered by owner label and project.
- **Budget:** limits the serialized JSON context by character count, skipping oversized records instead of truncating evidence invisibly.
- **Scope:** candidate pool is recent records (default 500 each from memory and decision tables), not an exhaustive semantic search over all historical context.
- **Provenance:** decision source labels are returned with `source_verified=false`; no claims of authoritative citations.
- **Tests added:** eight synthetic scenarios for relevance, latest-only decisions, owner/project scoping, deterministic budget, oversized-record exclusion, invalid inputs, and persistence.
- **Verification:** [GitHub Actions #41603654276](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41603654276) succeeded on Ubuntu and Windows at code commit `924588465a6eba43d11df70b49b955eda9c77762`: 29 unit tests (21 existing + 8 new), plus memory/backup/restore CLI checks.
- **Risks:** character limits are **not token limits**; lexical matching can miss synonyms and older memories; owner labels are not authentication; text is untrusted and must never be treated as model instructions.

### Checkpoint 05 validation repair
- First GitHub run failed because a synthetic oversized test record had 20,008 characters, exceeding the existing 20,000-character `MemoryStore.add` validation. Production input validation behaved correctly.
- Corrected the fixture to remain within the store limit; no validation restrictions were removed.
- The next CI run passed on both operating systems.

## 2026-11-03 — Checkpoint 06: Context quality and missing-evidence signals
- **Implemented:** exact case/whitespace-normalized duplicate suppression for note records; identical latest decision evidence takes priority over duplicate notes. Distinct decision keys remain separate.
- **Diagnostics:** `matched`, `no_match_in_sample`, or `matches_exceeded_budget`. These are retrieval outcomes, **not** proof that a fact is absent.
- **Budget:** continues enforcing serialized JSON character limits, including diagnostic fields. No token counter is claimed.
- **Tests added:** six synthetic regressions for duplicate notes, decision precedence, distinct decisions, no-match diagnostics, over-budget matching evidence, and diagnostic length.
- **Verification:** [GitHub Actions #41604448473](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41604448473) passed on Windows and Ubuntu at code commit `f7fef0096d2f7c3b5067889cf6e36f84738ad616`: 35 unit tests (29 existing + 6 new) and CLI smoke checks.
- **Caveats:** deduplication is exact normalization only, not semantic similarity. Data scoping still uses untrusted caller owner labels, not authentication.

## 2026-11-03 — Checkpoint 07: Retrieval evaluation
- **Code:** `varyn/evaluation.py` runs six independent, labeled, synthetic scenarios with no external provider calls or real data.
- **Metrics:** positive hit rate, positive mean reciprocal rank (MRR), and correct rejection rate for negative cases. Denominators are included.
- **Expected baseline:** 2/5 positive cases found (40% hit rate and 0.4 MRR), 1/1 negative correctly rejected (100% in this one negative case). These are *fixture results, not evidence of real-world quality*.
- **Known failures intentionally retained:** Bahasa Indonesia synonym mismatch, older note excluded by recent-candidate limit, and a matching note too large for the character budget. We do not erase these failures to make the benchmark look better.
- **Tests added:** eight regression checks for metrics, individual scenarios, and JSON output.
- **Verification:** [GitHub Actions #41607148369](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41607148369) passed 43 unit tests (35 prior + 8 evaluation checks) and CLI smoke steps on Windows and Ubuntu at code commit `bef68fa6ca38f6b2f65fb22667aee7cde0bfc92e`.
- **Next:** improve retrieval quality with a measured intervention and expand the evaluation set independently before any accuracy claim.


## 2026-11-03 — Checkpoint 08: Lightweight bilingual retrieval pilot
- **Intervention:** six explicit Indonesian/English canonical-term mappings in `varyn/lexicon.py`; `varyn/context.py` applies the same normalization to queries and stored text.
- **Controlled comparison:** the existing six-case synthetic benchmark moves from 2/5 to an expected 3/5 positive hits (40% -> 60%, MRR 0.4 -> 0.6); one negative scenario remains correctly rejected (1/1). These are tiny hand-designed fixtures, **not** a real-world accuracy improvement estimate.
- **Known unresolved misses:** candidate-pool exclusion and oversized evidence still fail in the benchmark. Unlisted synonyms such as `arsip` are not handled.
- **Independent checks:** six additional positive/negative glossary tests, including cross-project/owner-label filtering.
- **Verification:** [GitHub Actions #41611678899](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41611678899) passed Windows and Ubuntu on code commit `08dd2502dcbc50d1f23acd5d979dbaac78c36423`: 49 unit tests (43 previous + 6 new) and existing CLI smoke steps.
- **Risks:** hardcoded aliases can create false positives; glossary is not semantic reasoning or machine translation. No authentication/encryption, and no model/provider calls.

## 2026-11-03 — Checkpoint 09: Disk-backed SQLite FTS5 memory indexing
- **Implemented:** `varyn/index.py` creates an SQLite FTS5 external-content index, one-time backfill of legacy memory rows, and insert/update/delete triggers for subsequent changes.
- **Integration:** `varyn/context.py` selects recent matching **search hits**, rather than only the latest written notes. Search expansion uses the existing small bilingual glossary, with quoted/parameterized FTS expressions.
- **Tests added:** nine synthetic regressions for historical recall, legacy backfill, insert/delete/update triggers, owner/project filtering, bilingual expansion, operator-like input, reopening, and many irrelevant records.
- **Controlled benchmark expectation:** 4 of 5 positives retrieved (80%), previously 3/5 (60%). One negative remains correctly rejected. One oversized record still fails to fit; percentages are from six designed fixtures and cannot describe real-world accuracy.
- **Verification:** [GitHub Actions #41612795744](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41612795744) passed on Ubuntu and Windows at code commit `c0b24bfebfe7a359df31415201fcc733f4b5eb7b`, with 58 unit tests (49 prior + 9 index tests) and memory/backup/restore CLI smoke checks.
- **Cautions:** FTS5 must be present in the local Python SQLite build. First index creation rebuilds on-disk index and may temporarily consume disk/CPU. No laptop performance benchmark, memory measurement, encryption, or actual authentication. Source annotations are unverified.

## 2026-11-03 — Checkpoint 10: Synthetic performance and memory instrumentation
- **Implemented:** `varyn/performance.py` builds a bounded synthetic dataset, times first-time FTS5 index creation, then runs repeated retrieval operations.
- **Measurements:** index build milliseconds; min/median/max query milliseconds; SQLite main-file byte sizes; Python `tracemalloc` peak bytes for index build and queries. Also asserts an old indexed note is retrievable.
- **CI:** runs the same synthetic benchmark on Windows and Ubuntu using 300 records and five retrieval repetitions per OS. Four small instrumentation regression tests added. No arbitrary speed threshold in the build gate.
- **Verification:** [GitHub Actions #41614154173](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41614154173) passed 62 unit tests (58 prior + 4 new), the synthetic benchmark, and CLI smoke checks on Ubuntu and Windows at code commit `c532fb7942dedf7f7aefa188e069eedd9dd793a1`.
- **Critical limitation:** `tracemalloc` does **not** measure total process RSS, SQLite's native allocation, other process activity, or Windows OS page cache. Synthetic CI runners do not represent the owner's own computer or available disk space. Disk numbers are for the SQLite main file only.
- **Safety:** does not modify or inspect the user's local files, does not download models, and consumes no paid API. Timing is informational, not a production performance guarantee.

### Checkpoint 10 CI performance observations (2026-11-03)
Dataset: 300 synthetic records, five retrieval repetitions; GitHub-hosted VMs, not the owner's laptop.

| Measure | Ubuntu hosted | Windows hosted |
| --- | ---: | ---: |
| First FTS5 index build, ms | 4.334 | 94.605 |
| Minimum query time, ms | 4.384 | 6.715 |
| Median query time, ms | 4.492 | 7.184 |
| Maximum query time, ms | 6.896 | 38.749 |
| Main SQLite file bytes before index | 86,016 | 86,016 |
| Main SQLite file bytes after index | 114,688 | 114,688 |
| Python-traced peak bytes during index build | 1,584 | 1,680 |
| Python-traced peak bytes during queries | 25,699 | 26,476 |

**Interpretation guardrails:** this sample does not measure process RSS, native SQLite memory, sustained throughput, CPU percentages, or warm/cold filesystem-cache effects. One run per OS with five repeats is not a statistically robust performance comparison. Runner CPU, SQLite versions, storage, and load differ. Not a promise of owner laptop speed or low RAM consumption.

## 2026-11-03 — Checkpoint 11A: Heuristic secret write guard
- **Implemented:** `varyn/safety.py` with a small, deterministic detector for recognizable private-key headers, common GitHub/OpenAI/AWS-like credential formats, bearer values and credential assignments.
- **Enforced:** `MemoryStore.add` and `DecisionJournal.put` reject matches **before** writing any SQLite row or decision revision.
- **Disclosure:** errors contain a fixed generic message, not the rejected input value.
- **Tests added:** six synthetic safety tests for detection, zero-write behavior, decision-source checks, ordinary content, deliberate false negative, and invalid types.
- **Verification:** [GitHub Actions #41614839681](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41614839681) passed **68 unit tests** on each of Windows and Ubuntu (62 previous + 6 new), plus synthetic performance and CLI checks, at code commit `f7b5e82baee6ba09aacab164ff0542d860b7b1f7`. Subsequent changes only update documentation and PR description.
- **Critical limitations:** heuristic checks can miss disguised or unknown secrets and can reject innocent text. Existing stored data is NOT scanned, erased, encrypted, or migrated. The database and backups remain plaintext, and caller-selected `owner_id` is NOT authentication. This is not a secure personal-data readiness gate.

## 2026-11-03 — Checkpoint 11B: Read-only storage exposure audit
- **Implemented:** `varyn/storage_audit.py` checks that a supplied path is an existing regular file, rejects symbolic-link paths, and inspects group/other POSIX file mode exposure.
- **Windows guardrail:** portable Python stat bits do not prove Windows ACL security. The audit explicitly reports `windows_acl_not_inspected` rather than inventing a successful ACL check.
- **Unconditional readiness gate:** `ready_for_sensitive_data=false` even when POSIX file mode is restricted. Encryption, real authentication, and a verified off-device backup policy remain absent.
- **Privacy:** report lists diagnostic codes only and never includes the local filename or file contents. Audit does not open/modify SQLite data or change file permissions.
- **Tests added:** eight synthetic regressions for existing/missing/non-file/symlink paths, privacy, POSIX permissions, and Windows ACL uncertainty. [GitHub Actions #41616816340](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41616816340) passed **76 tests** (68 prior + 8 new) on each of Ubuntu and Windows, plus benchmark/CLI checks, at code commit `8fad9ba981503949b9c4bce5cfaa38e86c4af677`.
- **Limitations:** checks are advisory; hardlinks, parent directory ACLs, Windows DACLs, symlink parent directories, and races are not fully assessed. Not safe for confidential data.

## 2026-11-03 — Checkpoint 11C-1: Experimental Windows-user-bound DPAPI envelope
- **Implemented:** `varyn/dpapi_vault.py`, a standalone Windows DPAPI seal/unseal facility using the operating system's current-user key protection. It handles bytes, not SQLite records or an app login.
- **New-file behavior:** encrypted bytes can be published to a fresh file without overwriting an existing path. No plaintext temporary file is intentionally written. File read rejects direct symlink paths.
- **Security tests:** eight tests covering invalid input, plaintext rejection, non-Windows fail-closed behavior, Windows roundtrip/tampering/file encryption/no-overwrite/symlink rejection. Some tests are intentionally skipped on the wrong OS.
- **Verification:** [GitHub Actions #41621003228](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41621003228) succeeded on Windows and Ubuntu at tested code commit `914120e45c4ef8e896f90ae7348d440af797f4fb`. 84 tests discovered per OS, with Windows-native DPAPI tests passing on Windows and skipped as intended on Ubuntu; existing performance and CLI smoke steps also passed.
- **Critical boundaries:** Existing `MemoryStore`/decision journals, backups and restore remain unencrypted SQLite and are NOT integrated with this facility. Windows account access is not a VARYN login; a compromised/logged-in account or administrator can access plaintext via process or DPAPI. Account/profile migration and key recovery are not solved; encrypted blobs may become unrecoverable on another PC/account. Python plaintext copies remain in process memory. Parent folder ACL, hardlinks and concurrent changes are not exhaustively validated. **Do not store personal sensitive data yet.**

## 2026-11-03 — Checkpoint 11C-2: Opt-in encrypted at-rest memory prototype
- **Implemented:** `varyn/sealed_memory.py` is a separate Windows-only, one-account `SealedMemorySession` that holds SQLite `:memory:` and its FTS index in RAM, then serializes the **complete** SQLite image and seals it with Windows DPAPI.
- **Persistence:** `save_new` always creates a new DPAPI-encrypted snapshot, never overwriting existing versions. Existing legacy SQLite database, journals and backups are not migrated or modified.
- **Validation:** reject plaintext snapshots, tampered DPAPI files, invalid SQLite headers, integrity check failures, schemas missing required memory fields and records outside the fixed local-owner label. Close handles on failed initialization.
- **Tests added:** ten total test methods across portability, re-opening, encrypted-file absence of plaintext, FTS persistence, immutability, tamper refusal, input guard, and versioned saves. Windows-native tests are skipped on Ubuntu.
- **Verification:** [GitHub Actions #41623353748](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41623353748) passed on Windows and Ubuntu at code commit `2b7fb0558ef41bc1ed79283ef6791cfa650f49f9`: **94 tests discovered per OS** (84 prior + 10 new), plus existing synthetic performance and CLI smoke checks. DPAPI whole-image roundtrip, FTS5 persistence and tamper checks passed natively on Windows, with native-only tests skipped on Ubuntu.
- **Limitations:** this is opt-in and supports basic memory add/search only. It does not yet integrate existing `build_context`, `DecisionJournal`, model adapters, restore/backup, user login, remote accounts or a recovery/export-key process. DPAPI protects *file-at-rest* under the Windows user profile, not memory in an unlocked session; data can be recovered by software operating as the same user. Saving is **explicit**, so closing without saving loses new notes. DPAPI envelopes limited to 1 MiB, and Python maintains plaintext in RAM when open. Additional OS/pagefile/crash dump protections and laptop acceptance are unverified. Real secrets are still prohibited.

## 2026-11-03 — Checkpoint 11C-3: Encrypted context & revisioned decisions (draft)
- **Integration:** `MemoryStore` and `DecisionJournal` now support explicitly borrowed SQLite connections, keeping their existing on-disk interfaces unchanged. `build_context` accepts the same connection to reuse the standard lexical + FTS5 + revision-aware retrieval engine.
- **Opt-in Windows session:** `SealedMemorySession` can append/history-read decisions, retrieve current decisions, and assemble project-bounded context from a *single* in-memory SQLite DB. Explicit `save_new` seals the entire image including decision revisions and FTS5 index into a new DPAPI file.
- **Validation:** encrypted snapshots containing decision rows for a different owner label or invalid decision table schema are refused. Old snapshots without a decision table are initialized without touching any legacy file.
- **Tests added:** 10 regression scenarios, including encrypted snapshot roundtrip, revision history and stale writes, project isolation, budget/dedupe, input guard, immutable earlier snapshots, use-after-close, tamper rejection, mismatched owner rows and borrowed-connection lifetime.
- **Verification:** [GitHub Actions #41624859520](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41624859520) succeeded on Windows and Ubuntu at tested code commit `948b2698020046be28e965fbe153c07218ae7b76`: **104 tests discovered per OS** (94 existing + 10 new), plus existing performance and CLI smoke checks. Native encrypted decision/context tests passed in Windows and were intentionally skipped in Ubuntu.
- **Limits:** Windows-current-user DPAPI is NOT application login. Explicit saves, 1 MiB image cap, plaintext in process memory, no key recovery or automatic backups, no migration of legacy database, no model provider or UI. Use synthetic data only.

## 2026-11-03 — Checkpoint 11D-1: Portable authenticated recovery prototype
- **Implemented:** `varyn/recovery.py` exports/imports up to 1 MiB of complete SQLite image using random-salt scrypt (N=32768, r=8, p=1; approximately 32 MiB KDF working memory) and AES-256-GCM with authenticated header. Uses the mature `cryptography` package (`requirements-recovery.txt`) instead of handwritten cryptographic primitives.
- **Portable:** the encrypted recovery file requires a separate user-held recovery passphrase, not the original Windows DPAPI user profile. Encrypted images can be authenticated/decrypted on Linux and Windows using the package.
- **Integrated:** `SealedMemorySession.export_recovery` writes a NEW portable encrypted export; passing `recovery_source` and `recovery_passphrase` on Windows restores the image in memory, validates memory/decision schemas and owner-label consistency, and optionally creates a new DPAPI snapshot via `save_new`.
- **Tests added:** 10 portable cross-platform cases (roundtrip, wrong passphrase, tampering, header, salt/nonce randomization, file/no-plaintext, no overwrite, input/size limits, symlink), plus 3 Windows-native integration tests (full memory/decision/FTS restore, wrong passphrase, invalid source arguments). [GitHub Actions #41626491782](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41626491782) passed **117 tests discovered per OS** (104 previous + 13 new), existing benchmark and CLI checks on Windows and Ubuntu, at code commit `24a63949c035c6427e7dde68fc4ce5085aae219e`. Portable recovery roundtrip passed on both; Windows-native recovery-to-DPAPI integration passed on Windows and was skipped on Ubuntu by design.
- **Boundaries:** A 16-character minimum alone does not guarantee password entropy; offline guessing remains possible. Losing the passphrase makes recovery impracticable. Portable recovery is **not** automatic and is not the same as a tested off-device backup strategy. Plaintext resides in Python RAM while opened. Neither the legacy plaintext store nor backups are migrated, encrypted or modified. No Windows account migration end-to-end test across separate real users/devices, no secure key escrow, no app login, and no protection from an unlocked/compromised account. Keep real secrets out.

## 2026-11-03 — Checkpoint 11D-2: Recovery integrity inspection and unsaved-write guard
- **Implemented:** `varyn/recovery_verify.py` decrypts an authenticated portable recovery into SQLite `:memory:`, checks SQLite `PRAGMA integrity_check`, required memory/decision columns and fixed local-owner labels, and returns non-sensitive record counts and status. It does **not** write plaintext to a disk file or expose record content.
- **Implemented:** `SealedMemorySession.has_unsaved_changes` tracks writes through the session API and `close_checked()` refuses to close when such writes have not been captured by a successful DPAPI snapshot or portable encrypted export. Failure to save leaves the session dirty and usable; existing snapshot is never overwritten.
- **Tests added:** seven recovery verification tests on Windows/Ubuntu, five Windows-only dirty-state tests. [GitHub Actions #41627317120](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41627317120) passed **129 tests discovered per OS** (117 previous + 12 new), synthetic performance and CLI checks, at tested code commit `9271e36c05012747a345a263fb4fdd826e3acaab`. Windows-specific unsaved-change tests passed on Windows and were skipped by design on Ubuntu.
- **Limitations:** `close_checked` is explicit opt-in; context-manager exit and regular `close()` still close without enforcing this gate. Abnormal process termination can lose edits. External/direct SQL writes are not tracked. Recovery inspection checks minimum schema/integrity, not full FTS correctness or independence of a second user/device. Snapshot size remains 1 MiB; no automatic backup, verified off-device copy or application authentication. All test data is synthetic.
