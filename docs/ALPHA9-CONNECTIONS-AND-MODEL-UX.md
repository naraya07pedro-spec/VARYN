# VARYN Alpha 9: actionable app connections + easier AI model selection

Owner-directed fixes from the actual Windows screenshots, 2026-11-06.

## The real start screen

Download Alpha 9, extract into a NEW directory (do not overwrite a running earlier build), verify the official release ZIP SHA-256, then run **VARYN-Portable.exe directly** as a non-administrator Windows account. The obsolete technical Tk root remains hidden from the main owner application (this was already fixed in Alpha 8).

## AI model selection

Open Home → **AI settings / Browse AI models**. Choose OpenRouter or DeepSeek.

- **OpenRouter:** select **Browse models**; the public `GET https://openrouter.ai/api/v1/models` catalog currently works without a key, but the provider may change this. Model results are provider-reported, not guaranteed callable by any account. You can also browse with an API key if public discovery fails. **Show $0 input/output models only** filters current provider-reported zero-priced records, not account entitlements or actual spending guarantees.
- **DeepSeek:** authenticated `GET /models` requires your own provider API key. Prices displayed are reviewed snapshots, not a billing cap or guaranteed provider quote.
- Select model, paste key locally if not already entered, review displayed input/output pricing, click **Use selected model**. This keeps the key in process RAM, not in GitHub, task DB or config.
- In the chat, explicit one-request network permission plus exact outgoing prompt review remains required for live inference. No automatic retry, extra calls, hidden file upload or implicit chat history sync.

## Real service connections (read-only VARYN operations only)

The Apps page now has interactive service cards with branded, locally rendered marks and Connect / Browse / Disconnect controls:

| App | Owner-authenticated API check | Deliberate resource listing |
| --- | --- | --- |
| GitHub | `GET https://api.github.com/user` | Up to 20 repositories from `GET /user/repos` |
| Notion | `GET https://api.notion.com/v1/users/me` | Up to 20 accessible pages/objects via `POST /v1/search`, read-only query |
| Netlify | `GET https://api.netlify.com/api/v1/sites?per_page=20` | Up to 20 owned/accessible sites; opens only validated `https://app.netlify.com/` URLs |
| Supabase | `GET https://api.supabase.com/v1/projects` | Up to 20 accessible projects; links built only from validated project refs |

No service is automatically connected. The owner must explicitly paste an independently issued personal access token. VARYN uses it for an account read and retains it in RAM only for the running application. Resource browsing is another deliberate, bounded API request. Provider tokens may allow **more privileges than these VARYN requests**, so prefer least-privileged or scoped PATs, especially for Supabase. Verified connection is **not** authorization for a general AI agent to execute writes, deployments, repo changes, database queries or private email actions.

Telegram is an actual separately configured owner-only Bot API long-poll channel. Alpha 9 fixes a functional defect in Alpha 8: the bot now receives the currently selected OpenRouter/DeepSeek API key from the in-memory model picker, rather than requiring a redundant environment variable / PowerShell launcher. Bot API token also stays in memory. Owner must supply BotFather token and their numeric Telegram ID, and each model request requires `/ask` followed by `/confirm CODE`. To avoid truncated approvals, question length is capped at 2,600 characters for this channel. No 24/7 uptime while Windows app is off.

WhatsApp, Gmail, Google Drive, Calendar, Slack and most other catalog entries still **do not have authenticated adapters**. Setup buttons only open official docs or clearly explain the absence of a connector. ChatGPT plugin/account access does not transfer to VARYN. Official WhatsApp Cloud API requires Meta Business access and a public HTTPS webhook with signature verification, which this Windows-only release does not provide.

## Desktop release verification

The first Alpha 9 push CI run `42227475122` was **cancelled** while running the inherited 100+ step Windows research suite, so no Alpha 9 ZIP was published from that run. This is NOT a passing verification.

The corrected workflow defines a focused, cross-platform **Owner UI + connector smoke** gate which compiles all Python source and runs the official adapter, model pricing/list, Telegram privacy, provider diagnostics, and actual Windows Tk owner-workspace tests. Windows Portable PyInstaller packaging, frozen synthetic GUI smoke, DPAPI separate-process persistence and full SHA256 manifest verification remain mandatory for release. The original exhaustive Windows/Ubuntu research suite remains in the workflow under **manual workflow_dispatch**, with a 25-minute timeout; its unexecuted status must not be called success.

A successful focused release gate demonstrates targeted code/GUI behavior and reproducible packaging, not comprehensive regression coverage or live owner-account acceptance.

## Validation boundaries

CI validates deterministic network-free synthetic provider responses and Native Windows Tk app construction, not an actual logged-in owner session. No API key, bot token, browser cookies, user memory or project files are committed to GitHub. Publicly offered ZIP is unsigned, not production certified.

Alpha 9 is not Hermes parity. A real agent execution runtime, multi-turn context, more provider integrations, signed installer, and operational gateway are future work. Owner's request explicitly defers any VPS work.
