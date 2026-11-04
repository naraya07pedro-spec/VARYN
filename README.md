# VARYN

**An open-source personal AI workspace for shared memory, multi-model collaboration, and reliable agent workflows.**

> **Experimental, non-production prototype.** Beyond the local SQLite memory experiment, this branch includes bounded context retrieval, opt-in provider API adapters, a Tkinter desktop, synthetic agent approvals and recovery, provider-native tool-intent adapters, and temporary read-only synthetic folder grants. These pieces are **not** an integrated personal AI product. There is no official ChatGPT/Claude/Gemini *app-history* bidirectional synchronization, no authenticated full agent permission boundary, no production-safe confidential storage, and no verified real-world autonomous execution. The default remains offline; paid API calls require explicit opt-in.

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

## Full-product goals that remain unimplemented

- Secure, user-authorized long-term memory and context usable across supported models. Current SQLite and desktop prototypes do not establish that security guarantee.
- Verified owner/user isolation and real OS-backed access control. String labels and UI confirmations are not authentication.
- Official-app conversation synchronization in both directions, only where providers expose documented supported capabilities. API calls and manual exports are **not** official-app synchronization.
- Reliable real agent execution with recoverable actions, authorized tools, and independent end-to-end acceptance evidence.
- Progressive local-first delivery without unapproved API spending or hosting costs.

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

### Checkpoint 15B: Opt-in native tool request client (experimental)

`varyn.native_tool_requests.native_tool_payload(provider, model, question)` creates provider-specific function declarations for exactly two synthetic local tools, `inspect_status` and `stage_note`. No external tool, arbitrary plugin, code execution, filesystem or network access is advertised to the model.

`NativeToolRequestClient` defaults to network-disabled. To request a provider tool proposal, the **calling application** must explicitly construct the client with `allow_network=True`, set the provider's API key as an environment variable, and pass `confirm_external_request=True` for that individual request and an existing `DesktopApprovalController`. This may result in paid API usage. The client reserves output-token budget before sending and refuses all local memory/context uploads. After receiving a valid response with one native tool call, it **only stages a preview**, never executes or grants approval.

This new code path is not wired into the Tkinter chat button yet. No real vendor account or API was used to verify request compatibility, tool availability or prices. The provider-specific API examples are source-backed by vendor documentation, not live interoperability tests. Do not use real secrets in prompts or rely on this for actual autonomous work.

### Checkpoint 16A: Read-only local file scope (standalone)

```python
from pathlib import Path
from varyn.scoped_files import ScopedLocalReader
reader = ScopedLocalReader(Path('/absolute/synthetic-demo-folder'))
print(reader.list_files())
print(reader.read_text('example.txt'))
```

Supply an **existing absolute folder chosen by the host**, not from model text. Only nonrecursive `.txt`/`.md` file basenames are accepted with strict UTF-8 decoding and byte limits. Originally this reader was standalone. As of 16C, the desktop UI uses it only for a synthetic filename count; it is **not connected to model tool calls**, has no filesystem write or network API, and is not an OS sandbox. Checkpoint 17C adds native Windows anchored reads without authorizing secrets or confidential files. Tests use synthetic folders only.

### Checkpoint 16B: Temporary read-only file grants

`ScopedFileGrants` manages host-created read-only directory grants. A trusted caller provides an existing absolute folder and asserts `user_confirmed=True`. The default scope expires after five minutes or ten operations, whichever comes first. A caller may revoke a grant. Failed accesses also consume operations, and the audit records only event type and a shortened ID, not paths or contents. The model cannot request these grants through existing VARYN tools.

This is **not proof of user authentication**, permission from a graphical dialog, or a secure Windows sandbox. Detected reparse points, hardlinks and Windows reserved names are denied, but OS-level handle/race protection remains incomplete. Only use synthetic test files.

### Checkpoint 16C: Desktop synthetic folder consent

**Historical behavior, superseded by checkpoint 17F:** The folder chooser described below has now been removed from the desktop, which only creates VARYN-owned disposable synthetic samples. This section remains as an implementation history, not current usage instructions.

The experimental Tkinter desktop now exposes **Grant synthetic test folder**, **Inspect test-folder count**, and **Revoke test-folder grant** actions. A trusted OS folder chooser and a separate explicit Yes/No dialog precede issuance of an ephemeral host-side read-only scope grant (default 5 minutes and 10 operations). The UI only shows a count of matching top-level test files; it does **not** display filenames or contents, attach files to a prompt, call models with folder data, or introduce file tools into the agent registry. Closing the desktop revokes active grants.

Only select folders containing **synthetic test data**. This is **not authenticated access control or an OS sandbox**. Checkpoint 17C mitigates Windows path-redirection risks with native pinned directory handles; it does not establish general process isolation or validate all adversarial Windows filesystems. Headless automated tests do not prove that a user physically clicked the dialogs. See [development log](docs/progress-log.md) and [official-app sync feasibility](docs/product-contract-and-feasibility.md).


### Checkpoint 17A: Official-app sync status and synthetic two-way reconciliation (offline)

The **Option C** goal remains to use official ChatGPT, Claude and Gemini apps with automatic two-way conversation/context synchronization. A model API, an export file or a provider's web UI is **not** evidence that official-app history can be read and written through an authorized synchronization interface.

Run this offline, no-auth diagnostic:

```powershell
python -m varyn.official_sync
python -m varyn.official_sync --provider chatgpt
python -m varyn.official_sync --provider claude
python -m varyn.official_sync --provider gemini
```

All three currently report `blocked_pending_provider_evidence` for automatic official-app history sync. This is **not** an assertion of permanent impossibility; it means that supported official-app read/write capabilities have **not been demonstrated** for VARYN. The referenced vendor guides explain export, not real-time authorized write-back.

`varyn.official_sync.SyncMarker` and `plan_synthetic_reconciliation(..., synthetic_fixture=True)` are an independent, **strictly offline fixture planner**. They only examine bounded synthetic IDs, revision numbers, digests and explicit tombstones. They never access a vendor, read a chat, write a file, execute a mutation, or authorize a model to modify app history. The planner refuses ambiguous deletions, conflicts, regressed revisions, and changed content without a revision increment. All candidate actions are review-only and have `can_dispatch=false`. No local or vendor text is included in its output.

**Safety:** the planner is not a sync engine or source-of-truth for real accounts. Treat actual provider support, ownership, deletion semantics, user consent, history API limits and vendor terms as separate evidence gates before attempting a live connector. See [product contract](docs/product-contract-and-feasibility.md) and [progress log](docs/progress-log.md).


### Checkpoint 17B: Scoped local reader handle lifecycle (experimental)

The standalone **synthetic-only** file reader now pins its approved directory to a POSIX file descriptor, then lists via the descriptor and opens files relative to the same directory with `O_NOFOLLOW`. This reduces the risk that a path swap between permission checks and opening a file will silently redirect reads to another directory. The descriptor is released when the reader closes, or when a temporary grant is revoked, expires upon attempted use, or exhausts its operation limit. Existing read-only size/extension restrictions remain.

**Historical 17B Windows limitation:** At this checkpoint Windows only rechecked parent reparse metadata and the root identity; it still had unanchored opens. **17C supersedes this specific gap** with native handle-relative Windows file opens and enumeration. The remaining limitations are authentication, full process isolation, native adversarial coverage, and actual laptop acceptance. None of this authorizes personal/financial/client documents.

To run the offline synthetic regression tests:

```powershell
python -m unittest discover -s tests -p "test_file_scope_lifecycle.py" -v
```

This reader is not exposed as a model or agent tool and still cannot write files or upload them to providers.


### Checkpoint 17C: Native Windows handle-pinned folder reads and inventory

VARYN now uses a separate **Windows native directory-handle backend** for the approved synthetic folder. The native scope pins the selected directory, opens child files relative to that handle via NtCreateFile + RootDirectory, enumerates via NtQueryDirectoryFile using the pinned handle, and rejects file reparse points, hardlinks, Windows device aliases, and unsafe filenames. It fails closed if native access is unavailable rather than reverting to pathname-based Python opens. POSIX retains the 17B directory-FD path.

A Windows-only CI regression suite exercises real native kernel calls, while the cross-platform suite verifies that non-Windows cannot open the Windows backend. No model tool is wired to file contents; the desktop displays only a bounded filename count, with host-approved temporary permissions. **This is not Windows account authentication or a secure process sandbox**. It remains limited to non-sensitive synthetic test folders until permission/authentication isolation, broader threat-model testing, and owner-laptop GUI acceptance pass.

See [native Windows threat model, evidence and laptop test steps](docs/windows-native-file-scope-17c.md) and the [progress log](docs/progress-log.md). The official-app synchronization target Option C is unchanged and remains unverified.


### Checkpoint 17D: Expired grants, Windows read stability, and local-only volume policy

The experimental, **synthetic-folder-only** scoped reader now closes stale Windows/POSIX directory handles when a trusted host calls the grant status endpoint, issues another grant, or revokes a grant. Expiration remains **opportunistic**, not timer-driven: if the app is idle without a status check, a handle may remain open until the next host action or process exit.

On Windows, the native reader now verifies file identity, metadata, size and last-write timestamp **before and after** reading. It rejects detectable concurrent changes, unexpected short/long reads, remote/mapped or removable volumes, and files with cloud-placeholder/remote-recall indicators. A path on a fixed drive can still involve a cloud service; these controls are **not** a guarantee against network access and do not establish OS-level process isolation, authenticated grants, or tamper-proof snapshots.

Run the new synthetic tests offline:

\`\`\`powershell
python -m unittest discover -s tests -p "test_grant_expiry_sweep.py" -v
python -m unittest discover -s tests -p "test_windows_file_consistency.py" -v
\`\`\`

No filesystem write API, model file access, or provider-account history synchronization was introduced. Never select sensitive folders. See [17D security and test notes](docs/file-access-17d.md) and [progress log](docs/progress-log.md).


### Checkpoint 17E: Idle-timeout closure for temporary synthetic folder grants

The Tkinter desktop now opts into a **single cancellable in-process expiry timer** for local file grants. When the app stays idle, the timer attempts to close the approved directory handle when its time limit elapses, rather than keeping it open until someone presses Inspect/Revoke. The timer is daemonized, metadata-only and never uploads, reads or writes user files. Existing headless library callers remain default-off for deterministic testing.

Generation-guarded callbacks cannot revoke newer permissions after a previous timer is cancelled. If an in-flight read or listing crosses its deadline, the manager **withholds the result**, even though a kernel read already underway cannot be interrupted. A failing/revoked/used-up grant cannot grant new access. **If the Python timer cannot be created or started, every grant in that manager is revoked and its directory handles are closed**, rather than silently continuing with non-expiring permission.

This is a **best-effort process-local timer**, not a secure OS sandbox or hard-real-time lease. During Windows sleep or when an operation holds the manager lock, handle closure may be delayed. The grant checks and failed-result handling prevent an expired operation from returning its result through this library. Identity-authenticated consent, untrusted-process isolation, owner-laptop hardware acceptance, and official-app Option C synchronization remain unresolved.

Synthetic test command:

\`\`\`powershell
python -m unittest discover -s tests -p "test_file_grant_idle_timer.py" -v
\`\`\`

See [17E scope/limitations](docs/file-grants-17e.md) and [running progress log](docs/progress-log.md). Never use sensitive folders with this experimental prototype.


### Checkpoint 17F: Desktop accepts only VARYN-generated synthetic fixtures

The experimental desktop file-demo button now **creates a temporary directory containing exactly two fixed non-sensitive files** (`sample.txt` and `notes.md`) after explicit Yes/No consent. It **does not open a folder picker** and cannot choose Documents, Downloads or other user-selected folders through this UI. The original read-only, time-limited and quota-limited grant still applies. When revoked, replaced, inspected after expiry, or on normal desktop close, the granted handle is closed and the fixture is cleaned up. **Historical 17F limitation, superseded by 17G:** ordinary expiry originally closed only the directory handle. Checkpoint 17G now also requests cleanup of its VARYN-owned temporary samples directly through the grant release lifecycle. Python timers remain best-effort and abrupt crashes can still leave harmless sample files.

This closes a meaningful gap between a *synthetic-only warning* and actual desktop behavior. It is **not** an OS process sandbox, authenticated Windows consent, or protection against same-user code. The trusted Python grant API remains experimental and callable by host code; it must not be exposed to model tool calls or sensitive inputs. Abnormal process death can leave benign temporary samples; physical laptop acceptance remains outstanding. No model or provider receives sample contents.

See [17F security guard and test evidence](docs/desktop-synthetic-guard-17f.md) and [progress log](docs/progress-log.md).



### Checkpoint 17G: Grant-owned cleanup for synthetic desktop sample files

The temporary demo files are now coupled directly to the lifetime of the **specific host-approved scoped grant**. A trusted-only, optional on_release callback closes the fixture **after** the pinned folder handle is closed on idle timer expiry, explicit revoke, replacement, revoke_all, quota exhaustion, read crossing its time deadline, or failure to start the expiry timer. This callback is never model-authored and no agent/model receives a filesystem tool. A once-only release flag and existing grant lock prevent double cleanup across timer/UI races.

SyntheticFixture.close() is protected by its own lock and retains its owner reference after a transient delete error so normal desktop shutdown can retry. The desktop no longer needs an Inspect or Revoke click to delete a sample after a successful idle-expiry callback. This is *best effort* during Windows sleep, process suspension or deletion failures, and **does not** clean up after sudden power loss or OS process death.

Additional Windows and Ubuntu regression suites test real one-second idle cleanup, concurrent revoke/timer access, fail-closed scheduler, and idempotent temporary directory cleanup. No private file access or provider app-history synchronization was enabled. See [17G evidence and limitations](docs/grant-fixture-cleanup-17g.md) and [development log](docs/progress-log.md).


### Checkpoint 17H: Real synthetic-only Windows self-check and official app feasibility

**No provider consumer-app account has been connected.** A reviewed, dated, offline-only evidence matrix now distinguishes the *actual official-app UI* capabilities of ChatGPT, Claude and Gemini: manual data export, memory import, chat history import, and unverified programmatic consumer-history read/write. ChatGPT exported chat upload is reference-only, Claude supports experimental manual memory import but not cross-provider full history import, and eligible Gemini Apps accounts support manual history and memory import. **None of these manual workflows proves automatic bidirectional sync.** The user-selected Option C requirement is unchanged and remains blocked pending provider-published evidence for supported official consumer-app READ and WRITE interfaces.

The desktop acceptance probe creates ONLY two disposable VARYN sample files. It exercises the platform's real scoped reader (including the native Windows backend), checks read-only listing, waits for a real one-second idle expiry, verifies automatic fixture cleanup and denies subsequent use. Its JSON report contains **no paths, names or file contents**, and explicitly states that it did **not** perform physical-user GUI clicks. It requires no AI provider, account credentials, network request, Administrator shell, or private files.

With an inspected source checkout in **normal PowerShell**:

    py -3 -m varyn.desktop_acceptance --synthetic-only --json

A source-only Windows ZIP now also includes **Verify-VARYN-Synthetic.cmd** for a double-click local self-test; it does not bundle Python or a compiled executable. Independently, the owner can run the GUI smoke command below and manually test the Tk UI with fake provider mode and generated synthetic files:

    py -3 -m varyn.doctor --gui-smoke --json

Passing hosted CI or the CLI probe is **not evidence of completed physical-PC GUI acceptance**.

See [official consumer-app feasibility evidence](docs/official-app-sync-feasibility-17h.md), [safe Windows acceptance steps](docs/windows-local-acceptance-17h.md) and [progress log](docs/progress-log.md). Do not import personal files, browser profiles, passwords or provider-account exports into this experimental desktop.


### Checkpoint 17I: Owner self-reported Windows GUI checks and native Option C proof gates

The source-only Windows ZIP now ships **Record-VARYN-GUI-Checks.cmd** alongside Verify-VARYN-Synthetic.cmd. The optional report launcher runs the existing synthetic-only CLI test, then guides the owner through six fixed yes/no/skip observations in a separate desktop window: opening VARYN in fake/network-off mode, declining demo consent, approving a two-file example, checking that no file contents/paths appear in chat, revoking, and restarting without restoring old permissions. The result is a bounded JSON status report, with NO raw answers, device identifiers, file paths or screenshots collected or persisted by this tool.

**This is an owner SELF-REPORT, not proof that software observed GUI mouse clicks or authenticated a Windows user.** Any missing, skipped or failed observation blocks even self-reported PASS. The report explicitly says independent owner-PC verification is false, and the source-only tool never upgrades privileges or connects AI accounts. No real files should be used.

From a normal (non-admin) PowerShell in the inspected VARYN source folder:

    py -3 -m varyn.owner_acceptance --synthetic-only --interactive

The separate offline Option C status utility enumerates seven required proof gates for EACH real official ChatGPT/Claude/Gemini consumer app, including supported consumer-app history read and write APIs, authorized identity, change detection, conflicts/deletions, account eligibility, and genuine end-to-end two-way owner acceptance:

    py -3 -m varyn.option_c_gate

**All provider gates remain blocked** because no verified supported native consumer-app history read/write interface has been established. This is a diagnostic, not a connector. A successful diagnostic exit code never means synchronization works. Manual Claude/Gemini transfers and model developer APIs do not satisfy the chosen Option C product requirement.

See [17I owner report and official-sync proof gates](docs/owner-acceptance-option-c-17i.md), [17H Windows steps](docs/windows-local-acceptance-17h.md) and [progress log](docs/progress-log.md). Do not enable private-file access or claim hardware GUI acceptance based on hosted CI.


### Checkpoint 17J: Real Tkinter button-command acceptance on hosted Windows

Beyond unit tests that call methods directly, VARYN can now **instantiate the real Tkinter desktop and exercise the actual Create / Inspect / Revoke ttk.Button callbacks** with no provider account, paid API or personal folders. The test initializes a fake-only controller with network consent disabled and an offline-only native tool client. It simulates decline/approval of the **generated synthetic demo folder** using test-controlled messagebox responses. It checks that the UI reports two example files without exposing their names/paths/content, that Revoke deletes the fixture and denies reuse, that a new one-second synthetic grant is cleaned automatically on idle expiry, and that reopening a fresh window does not restore old permissions.

Windows hosted GitHub Actions now runs this **real Tk widget command test as a required CI step**, with additional cross-platform tests that fail closed when buttons are missing/duplicated, graphics are unavailable, or errors could disclose private strings. The visible report distinguishes programmatic button invocation from physical mouse clicks or actual human approval.

To run locally on an ordinary (non-Administrator) Windows desktop with Python and Tkinter:

    py -3 -m varyn.tk_widget_smoke --synthetic-only --require-display --json

If no graphical session exists, the command fails rather than reporting success. A PASS means only that native Tk controls and synthetic permission flows behaved correctly in that environment. **It does NOT mean the owner visually inspected the app, consented to real file access, authenticated the OS user, or enabled official ChatGPT/Claude/Gemini bidirectional chat-history synchronization.**

See [17J Tk widget smoke and residual limitations](docs/tk-widget-smoke-17j.md) and [running progress log](docs/progress-log.md). The physical owner's normal Windows GUI acceptance checklist from 17I remains a separate step.


### Checkpoint 17K: Bounded three-role multi-provider collaboration engine

The module varyn/collaboration.py implements an actual staged **analyst -> critic -> synthesizer** handoff through VARYN's existing ProviderRouter and UsageBudget. Each stage explicitly selects a provider/model; later roles receive earlier role output marked UNTRUSTED, and their final synthesis is returned with per-stage metadata. Failure stops the chain: no implicit retries or fallback. The whole three-stage plan is preflighted for valid roles, available adapters, quota and explicit per-stage permission **before** any live request is dispatched.

**Default: offline and blocked from all live requests.** An application must opt in to each live stage, explicitly disclose that prior results will be shared across the chosen providers, and use external API credentials held outside source. Local quota is NOT a money/billing cap. The module is an engine, not yet an integrated desktop feature, and neither multi-provider invocation nor its output proves factual correctness or official consumer-app history synchronization. All-fake workflows and workflows using only one real provider never count as verified independent multi-provider review.

See [17K collaboration contract](docs/multi-provider-collaboration-17k.md), tests/test_collaboration.py and [progress log](docs/progress-log.md). Next: user-facing per-stage consent, shared memory handoffs, measured reasoning evaluation, resumable work.


### Checkpoint 17L: Three-role collaboration in VARYN desktop

The desktop **Collaborate (3 roles)** button now opens an explicit analyst/critic/synthesizer provider-and-model selection dialog. Default is fake/offline for all three roles. A live developer-model API stage is permitted only when VARYN network consent is enabled **and a separate UI confirmation is accepted for each live stage**, disclosing the original task, possible billing, and onward sharing of previous model outputs across the chosen providers. Any denial prevents the entire multi-stage request from dispatching. The run shares the ordinary chat's same in-memory request/output-token quota and reports all three roles plus synthesis in the visible transcript. Pending work runs on a worker thread and cannot be reliably canceled after provider dispatch.

This feature **does not** connect to consumer ChatGPT, Claude or Gemini chat histories, authenticate Windows user consent, fetch personal memory, or independently prove multiple model quality. A fake-only run merely verifies the UI-to-engine handoff and must never be described as genuine independent model reasoning. For normal-user Windows testing: \`py -3 -m varyn.desktop\` and use only generated synthetic prompts and fake providers. See [17L desktop collaboration implementation and evidence](docs/desktop-collaboration-17l.md) and [running progress log](docs/progress-log.md).


### Checkpoint 17M: Explicit local project memory in desktop (synthetic only)

VARYN Desktop now exposes **Local project**, **Save synthetic note**, **Search project notes**, and **Delete note ID**. They remain **disabled unless** the user launches the app with `--memory-db PATH` to opt into a specifically chosen SQLite database. For safe development on Windows, use `py -3 -m varyn.desktop --memory-db ".\\varyn-synthetic-notes.sqlite3"` from an existing writable directory. The UI requires an explicit Save confirmation, restricts input to fictional notes prefixed `SYNTHETIC:`, requires project-exact searching, and asks before deleting a project-bound note ID. These notes can persist across desktop restarts; ordinary chat history still resets and is NOT automatically stored.

**Important:** SQLite is presently **unencrypted**; the synthetic prefix does not protect secrets or verify content is truly synthetic. Do not save real personal, employment, financial or medical data. Memories are **never automatically loaded into messages, collaboration prompts, external provider APIs, or consumer ChatGPT/Claude/Gemini histories**. Current owner labels are not OS identity checks. This is groundwork for controlled multi-provider memory retrieval in 17N, not completed automatic cross-app history sync (Option C). See [17M memory scope and test plan](docs/desktop-memory-17m.md) and [progress log](docs/progress-log.md).


### Checkpoint 17N: Explicit selected memory in desktop collaboration

**New:** In the **Collaborate (3 roles)** dialog, users can optionally type **1 to 3 exact saved note IDs** from the selected local project. When and only when `--memory-db` was explicitly enabled, the context-sharing checkbox is on, all records belong to that exact project, and an additional memory-preview dialog is approved, the selected **SYNTHETIC-only** records become untrusted context for the **analyst** stage. Later models may indirectly receive note contents from prior-model outputs; each external API still requires its own separate confirmation. VARYN shows `memory:ID` references in the collaboration result. No automatic memory search, chat capture, background export or official consumer-app sync occurs. The underlying SQLite DB is **unencrypted**, so real private data must not be stored.

See [17N selected memory integration and limitations](docs/selected-memory-collaboration-17n.md) and [progress log](docs/progress-log.md). Live endpoints are developer-model APIs only and never replace the user's chosen official consumer-app sync Option C.

### Checkpoint 17O: Review and run a bounded synthetic task plan

The desktop **Run reviewed synthetic task plan (JSON)** button executes a user-provided, fully validated 1–6 step plan. It supports only `inspect_status` (read synthetic counters) and `stage_note` (write a synthetic note in RAM); each write requires a separate digest-bound on-screen approval. All steps are prevalidated, refusals stop remaining steps, no retries occur, and no shell/network/file-system tools are available. This is genuine deterministic sequential execution, **not autonomous LLM planning or a durable resumable agent**. A sample JSON plan and remaining limitations are documented in [checkpoint 17O](docs/task-plan-17o.md). The 17N syntax regression was repaired, but a green final Windows/Ubuntu CI run has not yet been observed for these latest changes.


### Checkpoint 17P: durable task status, no automatic replay

The existing synthetic task runner supports **explicit opt-in** metadata-only SQLite checkpoints when VARYN Desktop is launched with `--task-journal ".\\varyn-task-checkpoints.sqlite3"` in an existing local folder. It records a random task ID, plan digest, step cursor and lifecycle state, never the task's JSON, arguments, note content or approval tokens. Every step gets an uncertain checkpoint before execution and a completed marker afterward. On restart, unfinished tasks become `needs_review` or `needs_reconciliation`, **never automatically restarted**. The demo agent's in-memory notes are NOT restored. This is crash-awareness groundwork, not autonomous durable execution. [17P contract and limitations](docs/task-journal-17p.md).

CI additionally runs `tests/test_task_journal.py` on Windows and Ubuntu. A green final-commit CI result for 17N, 17O and 17P has not yet been confirmed through the available connector.
