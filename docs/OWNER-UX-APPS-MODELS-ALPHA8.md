# Alpha 8: one window, usable Apps, and straightforward AI model setup

November 6, 2026. This replaces the two-window, table-only and manual-model-ID experience documented by the owner's screenshots (Hermes Agent used as a benchmark).

## Daily UI

- **One visible desktop:** the legacy `VarynDesktop` Tk root now withdraws immediately in normal portable mode. It still owns the restricted gateway controllers and review functions but is not an overlapping window. Closing the user workspace also closes its internal root. The `--smoke-only` CI path remains independently guarded.
- **Model connection in three practical steps:** open AI settings, select OpenRouter or DeepSeek and enter your own provider API key. Click **Load models** for the selected provider's official `GET /models`, search by model name/ID, select a priced model and explicitly acknowledge its price/route before **Use selected model**. The chosen provider/model is displayed beside the composer. You do **not** manually type model IDs/prices if the provider supplies supported metadata.
- **Official listing is not free access:** OpenRouter prices are parsed from the provider's published API `pricing.prompt` and `pricing.completion` per-token values into USD per million; missing/invalid prices are not made up. DeepSeek's API model list currently does not expose prices; the dialog offers an explicitly labeled **2026-11-06 official peak (cache miss/output) price snapshot** for known model IDs, with a direct link to the official pricing page. Prices/availability can change. The local estimate is not an actual provider-enforced billing cap. No silent fallback.
- **RAM-only credentials:** a pasted AI key is not added to the process environment and is not persisted. Gateway now supports passing it directly into a single reviewed request. `TelegramChannel` can reuse this *in-process* model credential when the owner separately starts their bot. Existing OS environment launcher credentials still work.
- **Every real request** still requires one explicit network permission and exact prompt review. No auto-send or unreviewed memory injection.

## Apps instead of a decorative table

- The main Apps page is now a scrolling, searchable collection of clickable service rows with local vector brand markers (no remote image requests).
- Featured **Telegram** expands into the existing official Bot API connection fields.
- **GitHub** supports a manual owner token, an official `GET /user` connection check, and a separate owner-clicked read-only `GET /user/repos` list. Use a fine-grained token with minimal metadata/repository-read permissions.
- **Notion** supports a manual owner integration token, an official `GET /v1/users/me` connection check, and a separate owner-clicked `POST /v1/search` (documented read-only search operation) to browse accessible resource IDs.
- GitHub/Notion tokens remain in RAM and are cleared on Disconnect/closing the desktop. Neither adapter accepts write actions or inherits ChatGPT/Gmail credentials.
- The other visible catalog entries are clickable, but **not connected**; they open a fixed official documentation link where known, otherwise display an explicit 'not implemented' explanation. Clicking a setup guide is not establishing OAuth nor invoking remote tools.
- **WhatsApp is NOT connected**: the official Cloud API requires owner Meta Business authorization, number registration, and secured public HTTPS webhooks. No scraping or bypassing WhatsApp consumer sessions.

## What remains unimplemented

Hermes still offers more mature model routing, channels, background jobs, and durable agent sessions. This VARYN build is a useful interim product, not Hermes parity. No VPS, daemon, scheduled task executor, automatic third-party access, full OAuth/Gmail/Drive integration or continuous consumer chat synchronization. GitHub connection indicates the account identity only, not operational permission beyond the selected API calls.

Source maintained on the OPEN/DRAFT PR #1; no feature-source merge to `main`. Only publish a downloadable Alpha 8 after Ubuntu/Windows tests, the portable GUI artifact and GitHub prerelease publication complete. Real owner-account connectivity and screenshot fidelity remain to be verified on the owner's Windows machine.