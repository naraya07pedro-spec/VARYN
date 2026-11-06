# Alpha 12: five additional real read-only app connections

Owner-reported defect (2026-11-06): `More services` remained dominated by nonfunctional setup guides. This milestone implements working authorization probes and bounded read-only data browsers for five additional, distinct services. These do not reuse ChatGPT plugin sessions or invent app login.

## Newly implemented

| Service | Owner credential source | Authentication proof | Browse action | Required access |
| --- | --- | --- | --- | --- |
| **Slack** | https://api.slack.com/apps | official `POST /api/auth.test` verifies workspace + token | up to 20 accessible public channel names | Slack app token; `channels:read` for browsing |
| **Linear** | https://linear.app/settings/api | official GraphQL viewer query | up to 20 issue identifiers, titles and links | Personal API key; API can have wider access |
| **HubSpot** | https://app.hubspot.com/private-apps/ | official 2026-03 contacts API returns successful result | up to 20 CRM contact first and last names | Private app token; `crm.objects.contacts.read` |
| **Dropbox** | https://www.dropbox.com/developers/apps | official `users/get_current_account` identifies user | up to 20 file/folder names via `files/list_folder` | Scoped access token; `account_info.read`, `files.metadata.read` |
| **Discord Bot** | https://discord.com/developers/applications | official `GET /users/@me` with bot identity, rejects normal users | up to 20 guild/server names | Bot token only, no Discord user token or self-bot |

VARYN supports **Connect → Create token → paste token locally → Connect → Browse → Disconnect** for these apps. The service-specific token is retained only in the current Python process, never in JSON preferences, GitHub, SQLite, logs, or model prompts. Connections are marked Connected only after one real official API authentication check. VARYN does not create app OAuth clients or grant scopes itself. An existing token may be overprivileged, so prefer minimally scoped/short-lived tokens and revoke them at the source when done.

Provider endpoint calls use hardcoded official HTTPS URLs, reject redirects, limit response sizes, make no automatic retries, and sanitize provider errors. All browse actions deliberately require another owner click. Browsing returns only a small list of safe display labels and pinned provider-domain links. Provider content is **never automatically passed to a model**. Discord is explicitly a bot integration, **not** a standard user's Discord account session. Slack access depends on workspace app installation and scopes. Dropbox developer-console test tokens expire; owner must obtain a new token when necessary.

## Existing working connections

- GitHub, Notion, Netlify and Supabase: existing read-only PAT connections.
- Gmail, Google Calendar, Drive: existing owner-provided Google Desktop OAuth client + loopback PKCE flow. VARYN still lacks a verified VARYN-wide Google OAuth client and cannot offer public zero-setup Google login.
- Hostinger Email: existing IMAP TLS read-only header access.
- Telegram: separately configured official Telegram Bot API, owner DM allowlist, explicit provider-call confirmations.

## Still not implemented

LinkedIn, Canva, Descript, WhatsApp, ChatGPT Automations, Writing Style and ChatGPT Plugin Management are **NOT** connected. Most require owner-created OAuth integrations, provider approval, webhook, or platform-specific access that cannot be inherited from ChatGPT. They remain setup guidance or feature requests; do not treat their logos as authenticated connections. No automatic task execution, cross-app skill/action invocation, 24/7 VPS or background processes are provided.

## Evidence

- `varyn/more_api_connections.py`: actual scoped official API request adapters, sanitized token handling, predictable read-only resource lists.
- `varyn/app_hub_ui.py`: five working service buttons with status, token prompt, background API verification and Browse.
- `integrations/catalog.json`: five new `connector` entries, no claims of credential inheritance.
- `assets/brand_svg/linear.svg` and `assets/BRAND-LICENSES.md`: authentic locally packed Linear logo, CC0 Simple Icons source.
- `tests/test_more_api_alpha12.py` and Windows native GUI tests: no-network synthetic protocol behavior and visible actionable UI.
- CI performs focused Ubuntu/Windows tests, brand rasterization, Windows frozen portable smoke, checksum manifest, and GitHub release publishing. Legacy exhaustive research tests remain manually runnable and are not represented as passed.

**Owner-account acceptance remains unverified** without user-entered provider credentials. A successful build is not proof a live token works, provider scopes are sufficient, or an action beyond read-only browsing exists.
