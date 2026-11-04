# Checkpoint 17A: Official-App Bidirectional Sync, Evidence and Safety Contract

**Date:** 2026-11-04 (Asia/Jakarta)
**Status:** Offline capability report + synthetic reconciliation design **only**. No authenticated official-app connector.
**User product requirement:** Option C: keep using the provider's **official app**, with automated two-way conversation/context sync. This document does not redefine or downgrade that requirement.

## 1. External capability evidence (provider-authored documentation)

| Official app | Confirmed export route | Supported automatic read of official-app history via documented VARYN connector | Supported automatic write-back of official-app history via documented VARYN connector |
|---|---|---|---|
| ChatGPT | Export account/history via app Data Controls or Privacy Portal: https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data | **Not verified** | **Not verified** |
| Claude | Settings > Privacy > Export data: https://support.claude.com/en/articles/9450526-export-your-claude-data | **Not verified** | **Not verified** |
| Gemini Apps | Google Takeout for Gemini Apps data: https://support.google.com/gemini/answer/16920332 | **Not verified** | **Not verified** |

Claude's official export guide explicitly says exports cannot be imported into another personal Claude account. The documented export routes do not establish authorized, instantaneous write-back in any of these official apps. **"Not verified" is not "proved impossible"**: reevaluate when official provider documentation and permissions actually demonstrate the necessary endpoints. Do not assert undocumented app-history API behavior.

Model API interoperability is a different product property and cannot be substituted for official-app conversation synchronization. Browser scraping, intercepted sessions, password handling or third-party extensions are **not** authorized shortcuts. No export files or personal chats were fetched during this checkpoint.

## 2. Current safe proof: explicit capability gate

Implemented in varyn/official_sync.py. Command:

    python -m varyn.official_sync

For each provider, the result is blocked_pending_provider_evidence, with official_app_read_verified=false, official_app_write_verified=false, automatic_two_way_sync_verified=false and can_dispatch=false. It has no networking imports or credentials. This deliberately keeps an unsupported interface unavailable and visible instead of silently claiming that a model API or data export satisfies Option C.

**Limit:** The capability registry is presently code-defined, not a future-proof official provider discovery service. It must be rechecked against primary docs before any supported status is changed. Code asserting a true capability is not evidence on its own.

## 3. Synthetic three-way reconciliation contract

The planner receives three **complete fictional** snapshots: last-common-base, local and official-side. It validates record keys, revision numbers, SHA-256-shaped digests, explicit tombstones, size bounds and a caller-asserted synthetic-fixture flag. It compares by record ID and content marker, never by a live remote call. It never stores, prints, or transfers transcript bodies.

The planner refuses to infer deletion merely because a record is missing from a snapshot. It treats missing base records on a previously known ID as **incomplete snapshot**, not deletion. Explicit deletion markers become **review-required proposals**, not deletes. Different local/official edits, conflicting new items, regressed revisions, and content changes without revision increments are flagged for review, not last-write-wins. Identical contents do not produce an echo-loop action.

can_dispatch=false applies to the whole plan **and every individual decision**. Statuses like official_update_preview and local_import_preview are *simulated directional proposals*, not proof that an official app endpoint exists. Any operator reviewing such a decision has no in-module function capable of executing it.

**Limitations and adversarial counterexamples:** A digest is not provenance or authorization, hash collisions are not formally impossible, source-side revision monotonicity must eventually be established by actual provider identifiers, and two snapshots cannot infer edits missing from their capture. Full snapshots here are an assumed synthetic fixture contract, not an empirical property of vendor apps. Do not use this planner for live customer data, real deletion, imported account exports, or automatic writes.

## 4. Future live acceptance gates (all required, NOT PASSED)

1. Documented authorized official-app read and write mechanisms for the SAME provider, with supported scopes, account ownership and clear terms, including edit/delete semantics and permission revocation.
2. Explicit verified user consent for access and scope; credentials stored and rotated safely outside model prompts/logs; least privilege and device-local isolation.
3. Independently observed propagation: create and revise a non-sensitive test conversation in the official app, detect it in VARYN; write an authorized test change through VARYN and observe it back in the official app without manual export/import.
4. Controlled conflicts, deletion propagation, revocation, restart/resume, idempotency, out-of-order changes, one-to-many model fanout and rate-limit handling. No silent overwrite or delete.
5. A recoverable durable journal with authenticated provenance, encryption, audited failed operations, bounded retry/cost policies and regression tests across Windows and Ubuntu.
6. Hardware acceptance on the owner's Windows machine and a clear halt condition if no documented official write path exists.

The present checkpoint proves **none** of these live acceptance outcomes. It provides only an inspectable contract and offline regression tests to prevent confusing model calls with official-app sync.

## 5. Evidence and execution convention

Reference code: varyn/official_sync.py
Tests: tests/test_official_sync.py
CI: .github/workflows/memory-checks.yml
Progress log: docs/progress-log.md
Repository: https://github.com/naraya07pedro-spec/VARYN/pull/1

Keep main untouched. A passing test suite for a fake plan is **not** evidence of a working two-way connector. Record the exact CI run and head SHA separately from any subsequent docs-only commits.
