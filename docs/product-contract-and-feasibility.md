# VARYN: product contract, evidence, and official-app sync feasibility

**Reviewed:** 2026-11-04 (Asia/Jakarta)  
**Status:** Product contract and feasibility checkpoint; **NOT** a final architecture decision.  
**Source priority:** explicit user decisions from the prior "Ide AI Agent Universal" discussion, then live VARYN code/CI, then provider-published documentation. This is a selective reconstruction, not a verbatim transcript of all 50 question/answer pairs.

## 1. Non-negotiable product intent

- Product name **VARYN**. A local-first, single-owner personal AI workspace spanning GPT/ChatGPT, Claude and Gemini with transferable, durable context and reliable agent workflows.
- **Selected experience: C.** The user keeps using the **official provider apps**, while VARYN should synchronize conversations/context/memory **automatically in both directions**. Treat this as the product target. Do not quietly replace it with a VARYN-only chat application, provider API aggregator, manual exports, or one-way import.
- One public repository, `naraya07pedro-spec/VARYN`; credentials, private datasets and sensitive parts must remain private. Maintain a clear owner/user authorization boundary.
- Initial operation is **local-only**. If the PC is off, active execution stops; no covert cloud runtime. No unapproved paid API traffic, hosting, automatic merge, or invasive filesystem actions. High-risk effects require explicit permission.
- The prior 50 answers were consolidated into 15 areas: provider/synchronization; budget/quota; memory; collaboration; planning; autonomy/consent/human intervention; security/privacy/data; skill evolution/evaluation; reasoning/creativity; research/verification; computer/browser/apps; multimodal/UX; resilience/backup; testing/observability/auditing; local infrastructure/performance/portability.
- Prior consolidation favored core-first incremental delivery, official-first integration, lossless staged migration, evidence-gated acceptance, and bounded/self-healing maintenance. These describe **direction**, not proof of technical feasibility or authorization for paid services.

## 2. What the code currently proves, and what it does not

At VARYN PR #1 (draft, branch `feat/local-memory-prototype-20261103`), prototypes include SQLite memory, bounded lexical retrieval, versioned decisions, opt-in provider API adapters, a desktop GUI, a synthetic agent tool protocol and approval flow, metadata-only crash recovery, and short-lived read-only test-file grants. Automated tests use synthetic data and CI on Windows and Ubuntu.

**Crucial distinction:** Connecting VARYN to **vendor model APIs** does **not** demonstrate reading, writing, or changing chats inside the **official ChatGPT, Claude, or Gemini apps**. Similarly, an export or import mechanism is not automatic bidirectional sync. A model API key is not the same as a consumer app subscription.

The code's demo approval/token and temporary file scope are not OS-enforced security or user authentication. Local SQLite memory/backup protection and actual target laptop acceptance remain incomplete. Do not process personal/client secrets in the current prototype.

## 3. Official documentation feasibility audit (as of 2026-11-04)

| Provider official application | Supported route evidenced in docs | What it **does not establish** |
|---|---|---|
| ChatGPT | Official account data export including chat history through Settings/Data controls or privacy portal. https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data | A supported always-on, per-chat, write-capable official app synchronization API; automatic two-way propagation from external software. |
| Claude | Official conversation export for supported account types through web/Desktop Settings > Privacy. https://support.claude.com/en/articles/9450526-exporting-your-claude-data | A supported real-time official-app conversation create/update endpoint that VARYN may call for bidirectional synchronization. |
| Gemini Apps | Google Takeout export of Gemini Apps data. https://support.google.com/gemini/answer/16920332 | An official bidirectional app-history synchronization protocol. |

**Interpretation, not impossibility claim:** The cited official documentation verifies export paths. It does **not** supply the missing supported bidirectional app-history APIs. Such APIs might later be available or discoverable elsewhere, but acceptance is currently **UNVERIFIED / EXTERNALLY BLOCKED** for the requested C experience. Do not treat unsupported scraping, browser session hijacking, credential capture, or vendor terms violations as a substitute.

A future provider-specific capability should be accepted only with current official API documentation, permissions/terms check, a revocable consent model, and an end-to-end test showing an official-app-originated change appears in VARYN and a VARYN-originated change appears back in the official app without manual export.

## 4. Product gates, ordered by risk rather than spectacle

| Gate | Current evidence | Exit criterion |
|---|---|---|
| G0: Safe development | Draft PR, offline synthetic CI, no auto-merge | Keep tests green, explicit progress logs, no private data or unapproved costs. |
| G1: Local trusted baseline | Prototypes, no full Windows hardware acceptance | Signed/verified installer or source distribution, actual owner-laptop GUI/CPU/RAM tests, encrypted local identity/memory, recoverable state and safe backup/restore. |
| G2: Official-app two-way sync | **No demonstrated supported provider mechanism** | At least one provider: documented permitted read + write paths, bidirectional change propagation and conflict/deletion checks in the official app. No substitution with APIs that only query models. |
| G3: Cross-model collaboration | API adapters and bounded synthetic tools, not unified context | Authorized shared context, source provenance, no secret leakage, prompt-injection resistance and measurable cross-model evaluation. |
| G4: Real agent autonomy | Toy RAM-only tools and metadata recovery | Privilege isolation, authenticated consent, bounded side effects, real failure/restart acceptance, audit and rollback where possible. |
| G5: Portable/resilient long-term use | Partial offline backup/recovery | Confidentiality, verification and restoration on another machine, provider changes/limits, durable user-visible logs, explicit cost ceilings. |

**Governance:** Keep G2's target unchanged even while development proceeds on safe G0/G1 subcomponents. No automatic G2 certification from G1. Report external capability blockers rather than redefining success. Do not merge the draft PR into `main` until review and acceptance requirements are met.

## 5. External references in the four uploaded PDFs

- `KOMPILASI_29_PDF_LENGKAP.pdf`: various research guides on MCP/A2A, OAuth, agent state, consent and orchestration. Useful design references, **not** evidence of vendor app-history access.
- `MASTER_CREATIVE_REASONING_6_REPO_UTUH (1).pdf`: six repositories and a creative-analysis workflow. An archive/guide, **not** model training or proof of benchmark improvements.
- `MASTER_6_OPEN_SOURCE_KREATIVITAS_NATURAL_LENGKAP.pdf`: six repositories including DSPy, ParlAI, and writing benchmarks, with ZIP attachments that may not be indexed by project search. **Not** automatic runtime integration.
- `Storyteller_KODE_LENGKAP_TANPA_PENGURANGAN.pdf`: persistent story-bible, revision, continuity and dependency patterns. Transfer the **mechanism** (durable state + explicit dependencies + audit), not the novel-writing domain as an entire VARYN architecture.

No combined-PDF content was silently executed or inserted as live code. All imported code needs review, license checks, isolated tests and practical relevance.

## 6. Execution log convention

For every future checkpoint, log: date + ID, problem/gate, exact changed paths, test command and result **with commit SHA**, regression/failure details, what was *not* tested, security/privacy/cost impact, and explicit next gate. Keep `main` untouched until sign-off. Distinguish **code pushed**, **CI green**, **hardware-tested**, and **product-accepted**; these are different states.
