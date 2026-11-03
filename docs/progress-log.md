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
- **Verification:** CI pending at this checkpoint's initial commit. Real numbers will be recorded after jobs complete.
- **Critical limitation:** `tracemalloc` does **not** measure total process RSS, SQLite's native allocation, other process activity, or Windows OS page cache. Synthetic CI runners do not represent the owner's own computer or available disk space. Disk numbers are for the SQLite main file only.
- **Safety:** does not modify or inspect the user's local files, does not download models, and consumes no paid API. Timing is informational, not a production performance guarantee.
