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

### Checkpoint 11D-2: Inspect recoverability and guard unsaved changes

To inspect an existing **synthetic** encrypted portable recovery without writing plaintext to disk:

```python
from varyn.recovery_verify import inspect_recovery
report = inspect_recovery("portable.varyn-recovery", "synthetic phrase from test")
print(report)  # status/count metadata only; never record contents
```

To deliberately prevent ordinary code from closing a Windows session with unsaved API writes:

```python
from varyn.sealed_memory import SealedMemorySession
session = SealedMemorySession()
try:
    session.add("VARYN", "synthetic note")
    if session.has_unsaved_changes:
        session.save_new("synthetic-new-snapshot.varyn")
    session.close_checked()  # raises without closing if changes remain
finally:
    session.close()
```

**Limits:** `close_checked()` is opt-in and does not handle hard crashes, OS shutdowns, direct SQLite updates, or a default context-manager exit. The recovery verifier checks minimum database integrity and structure, **not** guaranteed ability to recover on another person's account or different hardware. Snapshot size is still limited to 1 MiB, no automated redundant backup exists, and sensitive information remains prohibited.

### Checkpoint 11D-3: Optional encrypted checkpoint after every write

Windows-only experimental synthetic-data example:

```python
from pathlib import Path
from varyn.sealed_memory import SealedMemorySession

directory = Path("D:/VARYN/synthetic-checkpoints")  # create manually first
with SealedMemorySession(checkpoint_dir=directory) as session:
    session.add("VARYN", "storage synthetic checkpoint test")
    print(session.last_checkpoint)  # new DPAPI-encrypted snapshot
    session.put_decision("VARYN", "drive", "storage on D", "fixture:example")
    print(session.last_checkpoint)  # another new encrypted snapshot
```

This is **opt-in**: previous manual saving remains unchanged. Each public write triggers full SQLite-image serialization and DPAPI encryption into a fresh file; prior files remain immutable. If a save fails, the public write raises an error but is **already present in RAM** and remains unsaved, so blind retries may duplicate records or create a revision conflict. Inspect `has_unsaved_changes` and retry *saving* to a new path instead.

**Not zero-data-loss:** file publication and OS caches cannot guarantee survival of abrupt electrical power loss. Disk growth is unbounded without a retention policy, and full-image encryption on every write adds CPU/I/O; no actual laptop power-loss acceptance test has occurred. Use only synthetic data, not private client data.

### Checkpoint 11E: Safe checkpoint inventory and limit

Inspect an existing directory of synthetic encrypted snapshots without touching its contents:

```powershell
python -m varyn.checkpoint_lifecycle --directory "D:\\VARYN\\synthetic-checkpoints" --keep-latest 10 --max-bytes 104857600
```

Output contains **only numeric counts and advisory status**, not file paths, names or record contents. It warns when checkpoints exceed a selected budget, but **does not delete anything** or claim that recovery is verified. Files must match exactly `checkpoint-<32 hex>.varyn`; all other files are excluded. Direct symlink checkpoint paths are rejected.

To prevent unchecked growth from the opt-in Windows checkpoint-on-write session:

```python
from varyn.sealed_memory import SealedMemorySession
with SealedMemorySession(checkpoint_dir="D:/VARYN/synthetic-checkpoints",
                         max_checkpoints=100) as session:
    session.add("VARYN", "synthetic only")
```

The count cap is checked **before** public memory/decision writes, so hitting the limit stops new mutations. The default cap is 100 only when a checkpoint directory is configured. This trades continuity of new writes for preserving all existing snapshots; manual investigation is required. No automatic rotation, secure deletion or reliable disk-space reservation is implemented. Directory race conditions and files outside the managed pattern remain limitations.

### Checkpoint 12A: Offline-tested AI provider contract

The standard-library `varyn.providers` module has two ways to execute the **same high-level interface**: `FakeProvider` for zero-network tests and a minimal `OpenAIResponsesProvider` for the official OpenAI Responses API. The default denies network access. Credentials are read only from the `OPENAI_API_KEY` environment variable when a real call is explicitly enabled.

```python
from varyn.providers import FakeProvider, OpenAIResponsesProvider

reply = FakeProvider().generate("Test the provider contract", model="fake-test")
print(reply.text)  # deterministic test reply; no paid inference

# LIVE opt-in example (may incur API charges):
# provider = OpenAIResponsesProvider(allow_network=True)
# reply = provider.generate("Explain this fixture", model="YOUR_SUPPORTED_MODEL")
```

To attach bounded, retrieved VARYN context, pass `context=session.context("VARYN","storage")` together with **`allow_context_upload=True`**. Without that second flag, uploading local memory is refused. The context text is labeled *untrusted* and placed in the user input, never a developer/system instruction; this does **not** make model prompt injection impossible. The adapter requests `store=False`, disallows tool calls and redirects, and uses fixed request/response caps. Generic errors do not echo raw API responses.

**Honest boundaries:** there is no completed live API integration test, no automatic provider routing, no streaming, no cost accounting, no integrated UI, no agent action loop, and no verified private-data security. A live opt-in request can cost money and transmit your input to a third party; please do **not** use real secrets or private client data yet.

### Checkpoint 12B: Explicit multi-provider routing

`varyn.multi_provider.ProviderRouter` selects exactly one provider (fake, openai, anthropic, gemini) for each request. It never silently fails over, so an API outage cannot automatically move your memory to another company.

```python
from varyn.multi_provider import ProviderRouter, MessagesProvider

router = ProviderRouter()
reply = router.generate("fake", "Synthetic demo", model="fake-test")
print(reply.text)

# To explicitly opt in to a real provider, configure its API key in your
# environment and use a router with one opted-in adapter:
# router = ProviderRouter(providers={
#     "anthropic": MessagesProvider("anthropic", allow_network=True)
# })
# result = router.generate("anthropic", "Synthetic demo", model="YOUR_MODEL")
```

Anthropic uses `ANTHROPIC_API_KEY`; Gemini uses `GEMINI_API_KEY`; OpenAI uses `OPENAI_API_KEY`. Local context requires a separate `allow_context_upload=True` even after network access is enabled. Full API request/response shapes are mock-tested only, and opting into a live request can incur fees. Official model names, availability and any provider policies should be verified before use. Provider errors have no automatic fallback, and untrusted memory text is not promoted to system instructions. No real secrets or private client data.

### Checkpoint 12C: Explicit in-process usage budget

```python
from varyn.multi_provider import ProviderRouter
from varyn.usage_budget import BudgetedRouter, UsageBudget

budget = UsageBudget(max_requests=2, max_reserved_output_tokens=64)
router = BudgetedRouter(ProviderRouter(), budget)
print(router.generate("fake", "Synthetic test", model="fake-test",
                      max_output_tokens=32).text)
print(budget.snapshot())  # aggregate counters, no conversation content
```

This wrapper reserves request count and **maximum output tokens** before dispatch. It does not retry, switch providers or upload local context without consent. Failed/uncertain calls are charged against the *local quota* conservatively even if remote billing is unknown.

**Not a monetary cap:** input tokens are not pre-reserved; output-token ceilings do not represent actual pricing. These counters live in one Python process and reset after restart. Calling the raw router directly bypasses them. Do not rely on this for controlling paid API bills, production usage or sensitive data; provider-side billing limits must be configured independently.

### Checkpoint 13A: VARYN Desktop MVP (offline simulation)

Launch from the repository root on a Windows computer with Python 3.12 and Tkinter:

```powershell
python -m varyn.desktop
```

The lightweight Tkinter window shows a transcript, text input, a provider/model dropdown, two permission switches and request/token-reservation counters. **Only FakeProvider responds in this stage.** The OpenAI, Anthropic and Gemini options are *UI previews* and are hard-blocked, including when the network permission checkbox is selected. This is not a paid chatbot or a live API connection yet.

No history is saved by the desktop; everything in the session is held in RAM and lost when the window closes. The app never loads local memory automatically and does not request API keys. Use synthetic data only. `python -m unittest discover -s tests -v` runs controller tests without needing a display. Running Tkinter in a graphical Windows session and measuring actual UI responsiveness/RAM on the target laptop are still outstanding checks. No installer, account login, agent execution or real provider chat has been built.

### Checkpoint 13B: Optional live desktop chat

Run `python -m varyn.desktop` on a Windows graphical desktop. Safe startup stays in FakeProvider mode with networking unchecked.

For an explicit live request, choose OpenAI, Anthropic or Gemini, provide a supported model ID, enable network consent and approve the separate confirmation dialog for **each** request. API keys are read from the respective `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` environment variable. No keys are entered into the desktop.

Tkinter stays on the main thread; a background worker performs the selected provider request and the window polls a result queue. No local memory/context is read or attached automatically. Calls run through in-process quota, **not** a money spending cap. Closing the window cannot cancel an already dispatched remote request, which may still be billed.

**Not production-ready:** live endpoints and keys have not been verified against real accounts, GUI rendering and laptop RAM are untested, transcript remains volatile, and storage security is incomplete. Use only synthetic prompts; never paste client secrets.

### Checkpoint 13C: Desktop lifecycle and RAM probe

The desktop now supports **Discard pending reply** while a provider call is running. This hides its later response and prevents that response from repopulating in-process history. Closing the window with a pending request shows a warning. Neither action can cancel a request already delivered to a third-party model, and API charges can still apply.

For an entirely offline, bounded Python allocation probe:

```powershell
python -m varyn.desktop_perf
```

This uses FakeProvider and `tracemalloc` and prints current/peak Python allocation bytes for the sample workload. It does **not** measure process RSS, native Tkinter memory, device-wide RAM, or GUI render responsiveness. Actual acceptance on the target Windows PC is still required. No API calls are made during the probe.

### Checkpoint 13D: Windows launcher and offline preflight

Windows now has a root `Launch-VARYN.cmd` double-click launcher. It starts from its own folder, preferring `py -3` and falling back to `python`. No administrator access, Ollama, VPS or paid API is needed for offline FakeProvider mode. Python with Tkinter must already be installed; this is a **source launcher**, not a packaged EXE.

Offline environment diagnostic (no API keys read, no networking):
```powershell
python -m varyn.doctor --json
```
Run the **actual GUI smoke test only in an interactive desktop session**:
```powershell
python -m varyn.doctor --gui-smoke --json
```
The doctor reports resident memory of the **doctor process**, not the main desktop application. It cannot certify the 8GB laptop's real-world GUI RAM footprint or responsiveness.

Build a new deterministic desktop source archive from the repository root (destination must not already exist):
```powershell
python -m varyn.package_desktop --output varyn-desktop.zip
```
The ZIP contains only Python source files, README and launcher. No Python interpreter, installed dependencies, API credentials, local model, SQLite data or installer is included. Windows GitHub Actions publishes the same source ZIP as a short-retention artifact when CI succeeds. **Do not enter real client data** while encryption/authentication acceptance remains incomplete.

### Checkpoint 14A: Synthetic bounded agent (no live actions)

```python
from varyn.agent_runtime import BoundedAgent

agent = BoundedAgent(max_steps=3)
status = agent.propose("inspect_status", {})
print(agent.execute(status.proposal_id))

note = agent.propose("stage_note", {"text": "synthetic demo only"})
# Simulation of explicit approval; not proof of user identity:
approved_token = agent.approve(note.proposal_id)
print(agent.execute(note.proposal_id, approval_token=approved_token))
print(agent.snapshot())
```

This prototype **does not accept automatic AI-generated tool calls**, execute shell commands, access local files or network, install arbitrary plugins, or write persistent data. Only a fixed read-only status tool and an in-memory synthetic note tool exist. Its `approve()` call is not authenticated and is not yet wired to a real desktop confirmation, so the current behavior is **not a production-grade human-approval boundary**. Never use real client data, credentials, or destructive tasks in this agent.

### Checkpoint 14B: Desktop demonstration of agent approval

In the Tkinter desktop, click **Demo agent approval**. A dialog shows the exact tool, proposal ID, SHA-256 digest, action summary and risk before asking for a Yes/No decision. Yes approves and executes the fixed synthetic `stage_note` action in RAM, and No rejects it without executing. Closing the UI rejects any pending previews. No model output is used to create this action, and there is no shell, filesystem or internet tool.

The dialog is a **demonstration of the human-decision flow**, not real user authentication or protection from a malicious Python caller. The underlying `BoundedAgent.approve()` method is still callable in code. Neither approval nor the agent's synthetic notes survive restart. Do not rely on this for privileged actions, real secrets or customer data.

### Checkpoint 14C: Structured tool intent review (offline, proposal-only)

For a strictly synthetic manual UI test, paste this exact JSON into the desktop message box, then click **Review structured tool intent (untrusted JSON)**:

```json
{"format":"varyn.tool_intent.v1","tool":"stage_note","arguments":{"text":"Synthetic agent proposal demo"}}
```

The parser checks format, tool allowlist, argument shape, duplicate keys and size. It only **stages** a proposal for the desktop approval dialog; it does not automatically execute, query a provider, use tools, or grant approval. A user decision on the exact proposal ID and digest is needed before any synthetic RAM note is written. All read-only tool proposals also require an explicit UI decision in this workflow. Fields such as `approved`, `approval_token` and `execute` are refused.

This does **not** yet parse or connect native function-call envelopes from live OpenAI, Claude or Gemini APIs. It provides no authenticated human permission boundary, external automation, real files/network tools, persistent agent state or production security. Use synthetic data only.

### Checkpoint 14D: Opt-in crash/restart journal (metadata only)

To turn on durable **metadata-only** agent recovery, from an existing writable folder launch:

```powershell
python -m varyn.desktop --agent-journal agent_recovery.sqlite3
```

The app records proposal ID, tool, SHA-256 digest, state and timestamp in a local SQLite journal. It **does not** store tool arguments, messages, synthetic note contents, API credentials, responses, approval tokens or conversations. Without `--agent-journal`, desktop approvals are still RAM-only.

On process restart, unresolved proposals become `needs_review` and uncertain dispatched actions become `needs_reconciliation`. A startup note reports these counts. **Nothing is resumed, dispatched, approved or retried automatically.** If an external action is uncertain, verify its effect manually before attempting a new proposal; the old pending proposal cannot be resumed from metadata alone.

The SQLite file contains unencrypted metadata, including digests and tool names. Use a private local folder, **synthetic data only**, and never treat it as secure storage for customer information. Real power-cut durability and graphical laptop acceptance are not yet proven.

### Checkpoint 15A: Provider-native tool-call response normalization (offline only)

`varyn.native_tool_calls.parse_native_tool_call(provider, response)` accepts one completed function/tool-call in the **native response shapes** of OpenAI Responses, Anthropic Messages and Gemini generateContent. `stage_native_tool_call(provider, response, approval_controller)` stages the validated intent into the existing desktop approval controller, **without executing, approving, calling a live provider or loading local memory**. Exactly one registered synthetic tool call is permitted per response. Multiple tool calls, Markdown, text-only responses, unknown tools and forged approval fields are rejected.

This checkpoint does **not** configure the live network adapters to advertise tools or receive native function-call responses from real services. Those are subsequent tasks, as are real tool permissions and a UI that reviews actual model-originated proposals. The mock payloads validate parser behavior, not vendor compatibility or end-to-end safety. Keep all tests synthetic.
