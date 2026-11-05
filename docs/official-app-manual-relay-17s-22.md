# VARYN 17S-22 | Manual relay in the actual ChatGPT, Claude, Gemini apps

Date: 2026-11-05. **Implemented: user-reviewed clipboard and RAM-only reply relay. NOT implemented: automatic official consumer-app two-way sync (Option C).** PR #1 remains OPEN/DRAFT; main unchanged.

## What this stage changes

Previously `varyn.official_sync` and `varyn.option_c_gate` could only explain why supported automatic consumer history read/write was unverified. 17S-22 introduces a **real user-mediated handoff workflow** while preserving the actual target: native official ChatGPT, Claude, and Gemini applications, not a replacement chat UI or API-only shell.

`varyn/official_manual_relay.py` implements `OfficialManualRelay` with an in-RAM, three-hop, single-pending-copy state machine. It prepares a small text packet for the selected official application, clearly labels the user-written task and, when present, a prior user-pasted unverified reply. This is bounded text, not a tool call. Every packet has a random request ID, SHA-256 digest, fixed destination domain and 90-second approval TTL. All state resets at desktop close. No filesystem input, browser automation, credential extraction, background requests, provider account tokens, API calls or recurring sync.

`varyn/desktop.py` adds explicit selection (`chatgpt`, `claude`, `gemini`) and three buttons:

1. **Review and copy task to official app:** reads only text explicitly typed into the desktop Message field, presents the **complete packet in a scrollable read-only Tk modal** with digest, and copies to the OS clipboard only after the user selects Approve. Denial does not modify clipboard. The user opens their existing official application themselves and pastes manually. Clipboard may remain after VARYN closes; no private documents or secrets should be included.
2. **Review pasted reply (RAM-only):** the user manually pastes a short response back into the desktop Message field. A second scrollable modal shows the entire text and digest; accepting marks it as **unverified, user-asserted provider provenance**, stored only in VARYN RAM. It can be included in the next user-approved packet as quoted, untrusted reference text. It does **not** import native application history or memory.
3. **Discard manual relay RAM state:** deletes staged reply and pending relay state. It does NOT clear the OS clipboard because that could overwrite unrelated content; the user should replace clipboard content manually if needed.

This is a deterministic manual continuity mechanism, **not automatic two-way sync**. The browser or installed app may perform networking independently after the user pastes. VARYN does not know whether a packet was pasted or answered unless the user explicitly returns a reply.

## Confirmed official user-facing capabilities (public documentation review, 2026-11-05)

- **ChatGPT:** qualifying accounts can request an export from Data Controls; a ZIP may take time to arrive. Exported conversation files can be uploaded as reference in a new chat, but do not restore the original sidebar history, memories or account state. Docs: https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data and https://help.openai.com/en/articles/9106926-transfer-exported-conversations-between-chatgpt-accounts.
- **Claude:** supports a user-initiated cross-provider memory import and export flow; memory import is experimental and can omit details. This does not demonstrate an automatic consumer chat-history read/write connector. Docs: https://support.claude.com/en/articles/12123587-import-and-export-your-memory-from-claude.
- **Gemini:** eligible personal Google Accounts can manually import memory/preferences and other-platform chat history; restrictions include age 18+, account category and certain regions. These documented imports do not prove an unattended two-way sync API. Docs: https://support.google.com/gemini/answer/16868299?hl=en.

The absence of published read/write proof is **not** proof that no authorized interface will ever exist. App models' API access and official application histories remain distinct boundaries. `varyn.option_c_gate` must continue to block `can_dispatch` until the actual seven requirements are independently reviewed.

## Security limits and verification

- User-typed input is limited to 1,000 characters; pasted reply to 1,600; total transfer packet to 3,600. Control characters, unpaired Unicode surrogates, invalid provider names and more than three manual hops are rejected. Does not claim comprehensive secret scanning. User must avoid pasting private content.
- The clipboard is an OS-wide buffer, **not confidential storage**. No clipboard is read automatically; only exact explicitly approved output is written. A successful clipboard write does not prove a paste into any app.
- No claim that a user-asserted reply came from ChatGPT/Claude/Gemini. Prompt injection in pasted content is treated as untrusted reference; external models may still mishandle it.
- The existing provider API connectors are untouched and remain a separate opt-in path.
- Tests: `tests/test_official_manual_relay.py`, `tests/test_official_manual_relay_desktop.py`, `tests/test_official_manual_relay_tk.py`. Hosted Windows Tk tests exercise real widget commands using programmatic button invocation; they do NOT attest a human action on the owner's device. GitHub CI is required before calling the stage verified.
- The next product gate should include real owner-PC approval and visibility, the capability / permissions matrix for any newly documented official application integration, and no private automatic synchronization without supported read/write authority.

## Manual acceptance on the owner's PC

From a **normal-user (non-admin) Windows terminal** in a clean copy of the feature branch:

```powershell
git fetch origin
git switch feat/local-memory-prototype-20261103
git pull --ff-only origin feat/local-memory-prototype-20261103
py -3 -m varyn.desktop
```

Keep the VARYN provider as `fake`, with API and GitHub network consent OFF. Type a **non-sensitive sample task** in Message; select the official app target; choose `17S-22 | Review and copy task to official app`. Read the preview and click Reject once to prove the clipboard is not touched, then repeat and Approve. In your normal official app, paste and obtain a sample response. Copy that response back into VARYN's Message field, select `Review pasted reply`, and confirm only if the exact response is acceptable. Choose another target and preview the follow-on packet, which should label the earlier pasted reply as unverified. Finally, Discard manual relay RAM state and replace any remaining clipboard contents.

No physical owner-PC execution or provider account acceptance is claimed by the GitHub-hosted tests alone.
