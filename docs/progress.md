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
- Added six targeted synthetic tests. [GitHub Actions #41604448473](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41604448473) passed 35 total unit tests plus CLI smoke checks on Windows and Ubuntu.
- Did not add semantic matching, true citations, authentication, encryption, provider calls, or model token budgets.

## Checkpoint 07: retrieval evaluation
- Six labeled synthetic scenarios with explicit successes, misses and denominators.
- Expected baseline: 2/5 positive hits, 1/1 negative correctly rejected; benchmark intentionally exposes three known misses.
- Eight tests added. [CI #41607148369](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41607148369) passed on Windows and Ubuntu. Not representative of real user queries.

## Checkpoint 08: bilingual lexical pilot (3 November 2026)
- Added a narrow bilingual glossary, preserving all prior owner/project scoping and character budgeting.
- On the existing synthetic benchmark the expected positive hit rate is 3/5, compared with 2/5 before the change. [GitHub Actions #41611678899](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41611678899) passed 49 unit tests plus CLI smoke checks on Windows and Ubuntu.
- Added six independent glossary tests, including false-positive and isolation checks.
- This is not general multilingual semantic search and does not establish real-world quality.

## Checkpoint 09: SQLite FTS5 indexing
- On-disk FTS5 virtual table and triggers now support historical recall outside the latest write window, plus automatic updates and one-time backfill.
- Nine synthetic index tests added. Benchmark expectation on existing hand-labeled fixtures: 4/5 positive hits, 1/1 negative correctly rejected. [GitHub Actions #41612795744](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41612795744) passed on both Windows and Ubuntu.
- Indexing requires FTS5 support and additional on-disk space. First-use migration and performance on the owner's Windows laptop remain unverified.

## Checkpoint 10: Synthetic performance and memory benchmark (3 November 2026)
- Added a bounded benchmark for indexing and query latency, on-disk SQLite main file size, and Python-only peak tracked allocations.
- Added four instrumentation tests; scheduled a 300-note, five-query benchmark on CI for both Windows and Ubuntu. [GitHub Actions #41614154173](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41614154173) passed 62 unit tests and benchmark/CLI steps on Windows and Ubuntu.
- These metrics do not measure total native SQLite memory, full process RSS, or the actual owner's Windows laptop.

### Verified checkpoint 10 runner observations
- Ubuntu: index build 4.334 ms; median query 4.492 ms.
- Windows: index build 94.605 ms; median query 7.184 ms.
- Both: 300 synthetic notes, five query repetitions; database main file 114,688 bytes after indexing.
- Python-traced query peaks: 25,699 bytes (Ubuntu), 26,476 bytes (Windows). **Not total RAM or native SQLite allocations.** See chronological progress log for full measurement table and methodology.

## Checkpoint 11A: secret write guard (3 November 2026)
- Added deterministic credential-pattern refusal to memory and decision writes, using a generic error message.
- Six synthetic tests passed along with prior tests in GitHub Actions run #41614839681 on Windows and Ubuntu (68 tests total per OS).
- **Not encryption, authentication, comprehensive secret detection, or historical data cleanup.** Do not store actual credentials or private conversations.

## Checkpoint 11B: Read-only storage exposure audit
- Added diagnostics for unsafe/missing/symlink file paths and POSIX permission bits.
- Windows ACL security is intentionally reported as **unknown/uninspected**.
- Audits always return `ready_for_sensitive_data=false` because encryption and authentication are still absent.
- Eight tests added; [GitHub Actions #41616816340](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41616816340) passed **76 tests per OS** on Ubuntu and Windows, plus benchmark/CLI checks. Audit does not modify files or grant authorization.

## Checkpoint 11C-1: Windows DPAPI sealed-file experiment
- Added separate Windows-current-user DPAPI envelope for standalone byte blobs, with no-overwrite encrypted file publication.
- Eight synthetic tests added. [GitHub Actions #41621003228](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41621003228) succeeded on Windows and Ubuntu; native DPAPI tests passed on Windows and were skipped on Ubuntu as intended. 84 tests discovered per OS.
- **This does not encrypt the SQLite memory database or its backups and does not implement application authentication.** Windows account binding affects recovery/portability and does not prevent access from an already-compromised Windows session.

## Checkpoint 11C-2: Opt-in encrypted SQLite image
- New Windows-only in-memory SQLite store can save all its contents and FTS index as a DPAPI-encrypted immutable snapshot; no plaintext SQLite file is intentionally written.
- Does not touch or automatically migrate the legacy plaintext store, backup, restore, or decision journal. Explicit saves, limited to 1 MiB before encryption.
- Ten additional test methods; [GitHub Actions #41623353748](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41623353748) passed with 94 discovered tests on each of Windows and Ubuntu, with native-only tests skipped on Ubuntu. Not ready for private/secret data, Windows profile recovery, or production usage.

## Checkpoint 11C-3: Encrypted context and decision journal
- One in-memory SQLite connection is now shared by encrypted-session memory, revisioned decisions, and the existing context retrieval engine.
- Explicit DPAPI snapshot persists notes, decisions, history and FTS5 index together, with source labels still unverified.
- Added 10 targeted tests, including use-after-close, owner/project scoping and immutable revisions. [GitHub Actions #41624859520](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41624859520) passed 104 discovered tests per OS, including Windows-native DPAPI integration tests (skipped on Ubuntu by design).
- This does not migrate or secure the older plaintext database, provide identity authentication, or enable key recovery.

## Checkpoint 11D-1: Password-encrypted portable recovery (prototype)
- Added optional `cryptography` dependency for vetted scrypt + AES-256-GCM portable SQLite image recovery.
- Windows encrypted session can export a separate NEW recovery file and reopen it into RAM using a passphrase independent of its old DPAPI account.
- 13 synthetic regression methods added. [GitHub Actions #41626491782](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41626491782) passed 117 discovered tests on Windows and Ubuntu; Windows-native integration passed on Windows.
- Backup placement, passphrase strength/custody, device-migration acceptance, app authentication and secure data migration remain unverified. Still not ready for sensitive data.

## Checkpoint 11D-2: Recovery verification and unsaved-change guard
- Added read-only-in-memory portable recovery verifier: authenticated decrypt, SQLite integrity, minimum schema, owner-label consistency and metadata-only counts.
- Added opt-in `has_unsaved_changes` and `close_checked()` to help avoid silently discarding API-level writes on normal closure.
- Twelve additional tests (seven cross-platform recovery inspection, five Windows-only dirty-state). [GitHub Actions #41627317120](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41627317120) passed 129 discovered tests per OS and benchmark/CLI checks; Windows-only cases passed natively.
- Not automatic autosave, OS-level process-crash protection, FTS deep validation, secure identity, or verified real-device disaster recovery.

## Checkpoint 11D-3: Encrypted checkpoint-on-write (opt-in)
- A Windows sealed-memory session may now create a NEW DPAPI-encrypted snapshot immediately after each API-level memory or decision write using `checkpoint_dir`. The last successful snapshot is exposed as `last_checkpoint`.
- A failed checkpoint does not overwrite the previous snapshot; it raises and leaves the in-RAM write pending/dirty. Six new Windows-only tests. [GitHub Actions #41630117495](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41630117495) passed 135 discovered tests per OS; native checkpoint tests passed on Windows and were skipped on Ubuntu by design.
- Risk: full-image encryption on every write increases disk use, CPU and I/O; no retention policy, actual power-loss qualification or process-crash guarantee. Default behavior remains manual save.

## Checkpoint 11E: Safe checkpoint inventory and count cap
- Read-only inventory and no-delete retention advice; exact managed filenames only, no user data disclosed.
- Opt-in Windows auto-checkpoint sessions refuse new public writes before mutation when the configured snapshot count cap is reached (default 100).
- 11 additional regression tests (9 portable, 2 Windows-native); [GitHub Actions #41632086742](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41632086742) passed 146 discovered tests per OS with benchmark and CLI checks. Windows-specific guard tests passed natively.
- Not storage cleanup, validated recovery, disk-space guarantee or production data-security assurance.

## Checkpoint 12A: Model provider foundation
- Added `FakeProvider` (fully offline) and an opt-in OpenAI Responses API adapter with bounded payloads and generic errors.
- Network disabled by default; local context upload requires separate explicit opt-in. Context remains untrusted user-role data.
- 13 new regression/integration tests with synthetic fixtures; [GitHub Actions #41633484562](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41633484562) passed 159 discovered tests per OS (Windows and Ubuntu), including prior benchmark/CLI checks. No actual API call or cost was incurred.
- Existing provider support is not a production credential vault, prompt-injection guarantee or live API compatibility certification.

## Checkpoint 12B: Multi-provider routing (mock-tested)
- Added explicit Anthropic Messages and Gemini generateContent adapters plus a fail-closed router for fake, OpenAI, Anthropic and Gemini.
- Network remains disabled by default; a second opt-in is mandatory before retrieved local context is sent to an external model. No retry/fallback to alternate providers.
- Added 14 fully offline regression cases; [GitHub Actions #41634252271](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41634252271) passed 173 discovered tests per OS plus existing benchmark/CLI checks. No live provider inference or API charge.
- Model names remain caller-provided and actual provider availability/eligibility are not verified.

## Checkpoint 12C: In-process usage budget
- Added opt-in wrapper `BudgetedRouter` using lock-protected `UsageBudget` with max requests, reserved output token ceiling, and aggregate usage reports without content.
- Failed or ambiguous requests keep their reserved quota, so no silent retry/fallback can evade the budget. Eleven new offline tests; [GitHub Actions #41635271566](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41635271566) passed 184 tests per OS on Windows and Ubuntu, alongside existing benchmark/CLI steps.
- **Not money/cost assurance**: no persistent or multi-process enforcement, automatic price tracking, direct-provider bypass prevention or reconciliation with provider billing.

## Checkpoint 13A: Lightweight offline desktop MVP
- Built `varyn.desktop` (Tkinter) with offline fake chat, provider/model selection, network/context permission indicators and in-process usage status.
- `varyn.desktop_controller` denies all live-provider calls even if consent switches are on; no automatic upload, no persisted history, no API usage.
- 13 headless regression tests added. [GitHub Actions #41636463939](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41636463939) passed 197 tests per OS with desktop compilation and Windows Tkinter import smoke. Actual graphical UI rendering and laptop performance remain unverified.

## Checkpoint 13B: Opt-in live provider chat with nonblocking UI
- Desktop controller supports real-provider adapters when explicitly opted in, while the default controller remains offline. Network consent and a separate per-request confirmation are required before live calls; memory context still has its own gate.
- Tkinter requests run in a worker thread, results are delivered to UI via a queue and Tk-only polling, and the Send button is disabled during an in-flight request.
- Nine headless live-flow tests added. [GitHub Actions #41640350647](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41640350647) passed 206 tests per OS on Windows and Ubuntu, plus desktop compilation and Windows Tkinter import checks. Real provider API access, display interaction and laptop RAM remain unverified.
- Closing UI cannot cancel an already dispatched remote API call and may not prevent billing. Quota is not a monetary guarantee.

## Checkpoint 13C: UI lifecycle hardening
- Added request-generation lifecycle protection for stale replies and separate RAM-history invalidation upon clear/discard/close.
- Added user-visible "Discard pending reply" and close-with-request warnings. These **do not cancel the external request or prevent its billing**.
- Added bounded offline desktop Python allocation probe; [GitHub Actions #41668489358](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41668489358) passed **215 discovered tests per OS** with lifecycle tests and probe. Probe does not cover full process RAM or GUI rendering.
- Native GUI acceptance and real Windows laptop RAM measurements remain open.

## Checkpoint 13D: Desktop preflight and source packaging
- Added double-click Windows `Launch-VARYN.cmd`, offline Python/Tkinter process-RSS doctor, and reproducible source-only desktop ZIP builder.
- [GitHub Actions #41671709750](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41671709750) passed **225 tests per OS** and built source ZIPs on Windows and Ubuntu; Windows publishes a seven-day downloadable artifact. Ten new offline regression tests passed. The Windows doctor-process RSS was ~20.6 MB on CI, **not the GUI's total RAM**. ZIP byte identity between OS checkouts is not guaranteed.
- Windows laptop GUI interaction and total app RAM remain **unverified**. The ZIP is source-only and requires installed Python+Tkinter, not a one-click standalone EXE.

## Checkpoint 14A: Bounded synthetic agent runtime
- Fixed in-process tool registry: `inspect_status` (read only) and `stage_note` (mutates synthetic RAM notes). Untrusted proposals cannot invoke shell/files/browser/network or install tools.
- One-time approval token required for mutation; steps, pending proposals and note count capped; audit omits note contents and token.
- 14 offline regression tests; [GitHub Actions #41674800510](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41674800510) passed **239 tests per OS** on Windows and Ubuntu. Token issuer is callable from Python and **not authenticated** as a human. No model-to-agent execution or GUI approvals yet.

## Checkpoint 14B: UI demonstration of human approval
- Introduced a desktop approval bridge with exact proposal ID, digest, action summary and risk. The desktop `Demo agent approval` action opens a Yes/No dialog for a fixed synthetic in-RAM note only.
- Tokens are one-use, consumed without appearing in the GUI; explicit rejection and close invalidate pending previews. Eleven headless tests; [GitHub Actions #41677185493](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41677185493) passed 250 tests per OS on Windows and Ubuntu. Physical desktop clicks remain unverified.
- This is not authenticated authorization or model-to-tool access. Untrusted Python code can still bypass the demonstrative boundary, and graphical clicks remain untested on the user's laptop.

## Checkpoint 14C: Untrusted structured model intent (proposal only)
- Added `varyn.tool_protocol` exact `varyn.tool_intent.v1` JSON schema parser with duplicate-key rejection and strict allowed tool/argument validation.
- Added Tkinter **Review structured tool intent** button: it reads untrusted JSON from the text input and stages a review via the 14B approval dialog; it never executes tool calls automatically.
- Fourteen offline regression tests; [GitHub Actions #41678798880](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41678798880) passed **264 tests per OS** on Windows and Ubuntu. No native live provider tool-calling, real actions, authenticated approvals or persistent agents.

## Checkpoint 14D: Durable metadata-only recovery
- Optional SQLite journal records proposal identity, digest, tool, status and timestamp. Crash recovery marks pending proposals for new review and uncertain dispatched actions for reconciliation; **zero automatic replay**.
- Integrated into the desktop approval bridge, and the Tk app accepts `--agent-journal PATH`. Default is still RAM-only unless opted in.
- 14 synthetic cross-platform tests added; [GitHub Actions #41680888700](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41680888700) passed **278 tests per OS** on Windows and Ubuntu after correcting SQLite test cleanup on Windows. No persisted note contents, approvals, executable arguments, encrypted journal or automatic task resumption.

## Checkpoint 15A: Native provider response tool-call normalization
- Supports parse-only mock response shapes from OpenAI Responses, Anthropic Messages and Gemini generateContent, normalized to fixed registered VARYN tool proposals. Rejects multiple calls, forged/unknown tool names, duplicate JSON keys and oversized payloads.
- `stage_native_tool_call()` sends a proposal for review, **not execution**. Fifteen synthetic headless tests; [GitHub Actions #41682862672](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41682862672) passed **293 tests per OS** on Windows and Ubuntu.
- No native tool declarations are sent to provider APIs and no live API/desktop native-tool round trip has been tested. Model responses remain untrusted.

## Checkpoint 15B: Provider-native request-side tool declarations
- Added OpenAI, Anthropic and Gemini request builders for the exact two synthetic local tools, plus an opt-in client using existing bounded HTTPS transports, per-call confirmation, env-based credentials and a session quota.
- Response envelopes are staged for existing proposal review, **never automatically dispatched**. Fifteen synthetic transport tests added; [GitHub Actions #41683887775](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41683887775) passed **308 tests per OS** on Windows and Ubuntu.
- Native tools are **not enabled in the desktop chat UI** and no real API compatibility or paid call has been tested. No encrypted private-task persistence or real-world tools.

## Checkpoint 15C: Desktop native proposal review
- Desktop has a separate native-tool proposal action. A worker parses the selected provider response; only the UI thread may stage the current proposal after request identity verification.
- No memory export, automatic tool execution or model-issued approval. Ten new headless tests. [GitHub Actions #41688204257](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41688204257) passed **318 tests per OS** on Windows and Ubuntu; vendor accounts and GUI interaction untested.

## Checkpoint 16A: Scoped read-only local file foundation
- Added standalone `ScopedLocalReader`, restricted to a user/host-supplied absolute directory and top-level UTF-8 .txt/.md files, with size/list caps, no recursive traversal and no write/network APIs.
- **Not connected to AI agent tools or desktop**. Fifteen synthetic fixture tests; [GitHub Actions #41760389734](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41760389734) passed **333 tests per OS** on Windows and Ubuntu. Windows reparse-point/hardlink and concurrent path-swap threats are not fully blocked. Do not use with secrets or private data.

## Checkpoint 16B: Ephemeral local file access grants
- Host-only `ScopedFileGrants` requires explicit caller-asserted user consent, binds an absolute folder to a random grant ID, limits operations and lifetime, and supports immediate revocation. A bounded metadata-only audit excludes file content and paths.
- Windows checks now deny detectable reparse points, multiple-link file metadata and reserved device basenames. This is best-effort, not a hardened Windows OS sandbox.
- Sixteen synthetic tests added; CI pending. Grants are not connected to AI/desktop and no real user file was accessed.
