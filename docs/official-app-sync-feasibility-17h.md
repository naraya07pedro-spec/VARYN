# Checkpoint 17H: Official consumer-app synchronization feasibility

**Reviewed:** 2026-11-04 (Asia/Jakarta)
**Scope:** Primary-source public documentation. No login, browser automation, account access, paid API, or third-party session scraping was performed.
**Unchanged product contract:** VARYN Option C must preserve the user's REAL ChatGPT, Claude and Gemini consumer-app experiences, with future automatic bidirectional conversation/context synchronization across the official apps. Developer model APIs, VARYN-only chat, exports, uploads or a user-operated memory migration are NOT substitutes.

## Evidence matrix

| Official consumer app | Manual conversation/data export | Official manual memory import from other AI | Official full chat-history import from other AI | Verified programmatic consumer-history read & write | Automatic two-way consumer-app sync |
| --- | --- | --- | --- | --- | --- |
| ChatGPT | Documented for eligible accounts/workspaces | Not verified here | Export-upload is reference-only, does not restore original chat history | Neither verified | Not verified |
| Claude | Documented, eligibility varies | Documented, experimental | Official help says cross-provider full chat-history import is not currently supported | Neither verified | Not verified |
| Gemini Apps | Documented via Google Takeout | Documented with eligibility restrictions | Documented with eligibility restrictions, including continuing imported conversations | Neither verified | Not verified |

**Important distinction:** "Not verified" is NOT "proven impossible forever." The table is evidence from the currently reviewed documents; it does not claim exhaustive provider capability discovery. A manual, account-controlled UI import is a meaningful partial portability mechanism, but is **not automatic**, **not two-way**, and **not proof of a consumer history write endpoint**.

### ChatGPT

- Official guide explains requesting a user-data export through account Data Controls or the Privacy Portal. An export is user-driven and can take time to prepare.
- Official ChatGPT account-transfer guidance explicitly states that uploading an exported conversations file into a new chat only makes it referenceable; it does NOT recreate separate historical chats, sidebar or account memory.
- OpenAI developer Conversations API is a separate developer API resource. Its existence does not prove it shares or can write the signed-in ChatGPT consumer application's historical conversations.

Sources:
- https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data
- https://help.openai.com/en/articles/9106926-transfer-exported-conversations-between-chatgpt-accounts
- https://platform.openai.com/docs/api-reference/conversations

### Claude

- Official Claude data exports contain conversation/account information, with plan/workspace rules; they do not create automatic sync.
- Official Claude memory import/export exists in web and Claude Desktop and is experimental. Provider-derived memory may not be incorporated faithfully. Copying memory is not copying every original conversation.
- Official getting-started guidance says cross-provider **full conversation-history import** into Claude is not currently available.
- Anthropic developer Messages API is stateless multi-turn. It is not a verified API for inserting or retrieving existing Claude.ai app history.

Sources:
- https://support.claude.com/en/articles/9450526-export-your-claude-data
- https://support.claude.com/en/articles/12123587-import-and-export-your-memory-from-claude
- https://support.claude.com/id/articles/8114491-mulai-dengan-claude
- https://platform.claude.com/docs/en/build-with-claude/working-with-messages

### Gemini Apps

- Google Takeout supports user-initiated exports of Gemini data/activity.
- Official Gemini Apps Help now documents importing preferences/memory and **full chat history** from other AI platforms, for eligible accounts. Requirements include a personal Google Account, age 18+, and region availability. The official article says it is not available in EEA, Switzerland or UK and some Gemini surfaces.
- This is the strongest presently documented *manual consumer-app history portability* path of the three. It is still not a verified programmatic, continuously scheduled, bidirectional write/read interface for VARYN.
- Gemini developer Interactions API persists its OWN API interactions and is not evidence of access to Gemini Apps consumer chat history.

Sources:
- https://support.google.com/gemini/answer/16920332?hl=en
- https://support.google.com/gemini/answer/16868299?hl=en
- https://ai.google.dev/gemini-api/docs/interactions-overview

## Implemented in repository

- varyn/official_app_evidence.py contains a dated, offline-only, source-linked capability registry with separate manual export, memory import, chat history import, official consumer history READ API, official consumer history WRITE API and automatic sync fields.
- varyn/official_sync.py includes the new evidence in its existing non-dispatchable CLI and provider capability outputs, preserving its synthetic-only reconciliation semantics.
- tests/test_official_app_evidence.py asserts provider differences, remaining read/write blockers, evidence source URLs, immutability of returned data and no dispatch/network.
- The CI matrix explicitly reruns the evidence tests on both Windows and Ubuntu.

## Release gate and next decisions

1. **Do NOT claim Option C operational.** Consumer-app read/write authority, account-consented authentication, stable revision IDs, change subscriptions/polling, deletions, conflict semantics, rate limits, terms/privacy, and auditability are not jointly verified.
2. **Use official manual portability as an optional separate feature, not a substitute.** Gemini's history import and Claude's memory import are the highest-value user-operated partial paths, subject to actual account eligibility and privacy review. No account UI action was executed.
3. **Re-check primary provider documentation before any production connector.** Require concrete, provider-published evidence of supported consumer-app history READ and WRITE operations, with authorization and reconciliation guarantees. If one direction remains absent, the status stays blocked. No reverse-engineering private endpoints or stealing cookies.
4. **Parallel engineering only:** finish synthetic-only Windows hardware acceptance and OS process/consent threat-model verification while external provider capability remains unresolved. Keep the codebase reversible and draft-only.

**Verdict:** Partial manual cross-platform transfer is documented; full automatic native consumer-app bidirectional sync is still not verified. The user-selected target is preserved, not silently relaxed.
