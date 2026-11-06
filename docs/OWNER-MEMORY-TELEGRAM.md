# VARYN real Memory Import + Telegram Owner Bot (experimental)

2026-11-06, scope grounded against actual Hermes Agent documentation.

## What is implemented

### Local encrypted ChatGPT history import

The VARYN **Memory** page now:
1. Prompts the owner to choose a ChatGPT account-export ZIP or a local `conversations.json`. This is **not automatic account access**. In ChatGPT, the official path is **Settings → Data controls → Export data**. Download the export ZIP privately.
2. Parses only bounded user/assistant text from `conversations.json`, never extracts other archive members, ignores attachments and tool/system messages, and displays titles for explicit multiselect.
3. Prompts the owner before importing selected conversations. Selected excerpts (bounded per conversation) are saved in a Windows **DPAPI encrypted** snapshot under `%LOCALAPPDATA%\\VARYN\\imported-memory.varyn`. No plaintext SQLite files or raw export copies are created by the importer.
4. The **Search** field performs explicit lexical retrieval from the decrypted in-memory snapshot. Select a result and click **Insert context into chat** to prefill a clearly marked, *untrusted quoted reference* into the editor. It **never automatically goes to a provider**; the user must inspect and send it through the existing model approval process.
5. Records are deduplicated by exported conversation ID fingerprint. Exports with unconventional structures may be skipped. Current pilot limits: 64 MiB export, 48 MiB JSON member, max 300 selected conversations, 800 KiB encrypted snapshot. This is **not a full archive restore, not automatic ChatGPT Memory-summary export**, not semantic vector RAG, and not two-way sync.

Windows DPAPI ties the encrypted file to the same Windows account and profile. It is **not** malware protection, provider account login, or portable backup. Importing private ChatGPT history requires careful content review; don't import passwords, private customer data or unrelated people's secrets. Deleting original ZIP or encrypted snapshots remains the owner's responsibility.

### Real Telegram Bot API channel

On **Apps**, enter a token from Telegram's **@BotFather** (create with `/newbot`) and **your own numeric Telegram user ID**, then click **Connect Telegram**. The bot is **allowlisted to this single user's private DM**, not groups, unknown senders or anyone who knows the bot username. It starts only when owner explicitly clicks Connect; token stays only in process memory; no connector credentials are written to preferences or GitHub.

You must first select OpenRouter/DeepSeek in Chat and configure its **real model ID, prices and provider API key** using the existing owner launcher. Telegram uses that same reviewed offer and shared session budget. Commands:

- `/start`, `/help`, `/status`
- `/ask your question` returns the destination/model and a text preview.
- `/confirm CODE` within 120 seconds authorizes **one** real provider call (no automatic retries), with provider charges possible.
- `/cancel` drops the pending request.

The bot uses official Telegram HTTPS **long polling**, and discards the old Telegram update backlog at connection. It can reply only while VARYN and its connection thread are running on the PC. There is a deliberate per-session cap of 15 model calls and 3,500 output characters. No voice, image/file processing, group chat, scheduled delivery, cron, cloud always-on or shared multi-user agents. This is **not Hermes parity**.

The implementation does not route normal text to providers, does not read browser cookies, and does not reuse ChatGPT app tokens. The numeric ID is required to prevent unauthorized use. If a token leaks, revoke with @BotFather.

### WhatsApp: NOT connected

A secure WhatsApp Cloud API connector would require owner-controlled Meta WhatsApp Business configuration, official token and number ID, a public HTTPS verification webhook, signature validation, send permission and message handling. None of that is present in this release. Hermes may use its distinct WhatsApp bridge; that does **not** authorize VARYN to copy WhatsApp sessions or login cookies.

## Exact limitations and proof

Full E2E testing on the actual owner's Telegram account and Meta WhatsApp account remains **unverified** without their explicit credentials and interaction. Hosted unit tests use a synthetic Bot API transport. No test says a real account was connected. All prior app permission controls remain in place. Existing `main` source is not merged without explicit owner permission.
