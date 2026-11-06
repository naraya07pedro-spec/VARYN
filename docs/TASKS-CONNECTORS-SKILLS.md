# Task, Connector, Plugin and Skill Foundation

Date: 2026-11-06. Scope: foundation for a scalable personal assistant; not an imported ChatGPT account.

## Task ledger: no artificial total task limit

Use `python -m varyn.unlimited_task_store --db ./varyn-tasks.sqlite3 add --title "Review an issue" --due-utc 2026-11-07T08:00:00+07:00`, followed by `list`, `count` or `mark-due`.

The new task ledger uses SQLite with pagination, indexed due timestamps, status transitions, and an unbounded TOTAL ROW COUNT in application logic. This **does not mean infinite tasks**: disk, SQLite limits, operating-system resources and actual external service rate limits apply. Every item has bounded title/detail size; the due-state scanner is bounded to 1–200 items per invocation. It does not spawn threads, run scripts, call models, use connectors, or schedule a background daemon. `mark-due` marks an item due; it does NOT perform its action.

The existing `varyn/task_planner.py` remains a **separate** 1–6-step synthetic execution experiment; this change does not silently remove its per-plan bounds or connect the ledger to real tools. A real durable task dispatcher needs idempotent claims, retries, durable results, policy-gated connector execution, operator UI, and crash reconciliation. Recurrence and time-based automatic execution are NOT implemented in this change.

## Integration directory: discovery, NOT authorization

`integrations/catalog.json` lists connector names surfaced in the currently accessible ChatGPT tool environment, plus plugin/skill candidate categories. Each entry is explicitly marked `catalog_only`, `execution_enabled=false` and `credential_inherited=false`. The local module `python -m varyn.integration_catalog` enumerates names, but never contacts external services or imports ChatGPT sessions.

Current identified app connectors: GitHub, Gmail, Google Calendar, Google Drive (including Docs, Sheets, Slides), Notion, Supabase, Netlify, LinkedIn, Hostinger Mail, Canva, Descript, Instavar Video Templates, ChatGPT Automations, Writing Style, and ChatGPT Plugin Management.

A connector being visible in ChatGPT **does not authorize** an external VARYN process to impersonate it. It is technically impossible to automatically copy the current ChatGPT app connectors' authentication tokens into VARYN via this repository. Some products may offer official OAuth or API keys to create a new connection, but each adapter must be independently implemented with clearly restricted scopes, official terms, local secret handling and separate user consent.

The catalog records plugin/skill *candidates*, not downloadable third-party code, installed ChatGPT skills, or executable Python plugins. VARYN intentionally does NOT import arbitrary Python modules or fetch remote skills without review. Per-skill execution boundaries, provenance and signed package policy remain to be developed.

## Owner safety

- Default external actions: DENIED; all entries non-runnable.
- Tasks stored in local SQLite; no at-rest encryption. Use test/nonsensitive text only.
- No credentials, OAuth grants, access tokens, or model-provider billable calls are automatically inherited.
- No hidden daemon, real-time recurring schedule, cross-device background service, Gmail send, Drive writes, GitHub merges, plugin execution or consumer-app history sync.
- `main` remains unchanged; implementation is isolated on draft PR #1.

## High-value next implementation

Start with a **real authenticated, read-only GitHub connector** after a narrow owner-account consent, then integrate an approved task with its response and durable result. Afterwards build official OAuth Gmail/Drive and scoped Notion connectors, with explicit audit and refusal for high-impact writes. This is the path to operational capability, not just a large catalog.
