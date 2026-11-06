# VARYN 17S-43 | Owner-approved model ID discovery via official read-only `GET /models`

Date **2026-11-06 WIB**. 17S-42 proved the real frozen EXE's fake request, denial, legacy-provider offline state, and RAM cleanup in Windows CI. **17S-43 adds a genuine new capability for an owner to run on their own PC**: discover provider-claimed model IDs through an explicit, read-only HTTP request. It does not depend on importing private consumer histories or using any consumer-account session.

## Why this capability matters

Previously the owner had to guess an exact model ID and manually enter owner-reviewed prices before a real API trial. Now the owner can inspect an untrusted list from the provider, choose one exact ID, and separately review and enter **both** input/output prices. A model appearing in an API listing does **NOT** prove account entitlement, inference success, price, "free" status, upstream identity or provider availability. In particular **OpenRouter's /models listing may be accessible without proving API-key validity**. A model-list request may be subject to provider-specific limits, but VARYN does not claim a guaranteed no-cost entitlement.

## Owner workflow in the real Windows Portable EXE

1. Obtain a verified artifact from the exact SHA GitHub Actions run. Extract the **entire one-folder ZIP**; don't run as Administrator and don't disable Windows Defender or SmartScreen. Always read `README-PORTABLE.txt`.
2. If using OpenRouter, DeepSeek or a local authorized 9Router, create an official API credential yourself and set it in your **own Windows normal-user PowerShell session environment**, not in ChatGPT, a .env file or a GitHub issue. Names: `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`, `VARYN_9ROUTER_API_KEY`. The GUI never asks you to paste keys. Process-environment keys are accessible to processes with sufficient local privileges, so do not treat this as secure keychain storage.
3. Launch `VARYN-Portable.exe` as the same normal user in the inherited environment. From the main VARYN window, open **17S-40 | Model Control Center** and then **17S-43 | Discover model IDs (official GET /models)**.
4. Choose OpenRouter, DeepSeek or 9Router. The dialog's network toggle starts OFF; 9Router's upstream authorization is separate and OFF. The user's desktop must also explicitly permit the separate universal gateway.
5. Click **Review exact GET /models & request ONCE**. Only after an actual owner review and affirmative approval of the pinned host, method and data-scope does VARYN dispatch one GET from a background thread. Refusal, missing key, disabled network or disabled 9Router upstream blocks before dispatch. There is **no automatic retry**, failover or account import. The toggle is consumed and reset OFF after sending.
6. VARYN shows up to 60 **sanitized ID strings only**, not remote marketing copy, descriptions, claimed price or tool instructions. These remain **provider claims, not credentials or independently authenticated provider identity**.
7. Select one model ID and click **Use selected ID (pricing MUST be reviewed separately)**. The ID is staged in the main Model Control Center, but **both price fields are cleared**, review flags reset OFF and the gateway's network/upstream flags reset OFF. **No quote is registered or AI inference attempted** by selecting an ID.
8. To try an actual model, separately verify its current prices and restrictions using the official provider UI, enter both prices, approve price/route, add the quote, choose a bounded fictional `SYNTHETIC:` task and inspect the current Model Control Center's exact **Review & send ONCE** flow. This can incur real charges. Token-cost estimates are **not** a provider-billing spending cap. If the provider account is unavailable, stop; never work around blocked authorization by scraping consumer cookies.
9. After a locally parsed non-FAKE response, the existing **17S-41 metadata-only observation receipt** may be reviewed and saved as a **new JSON file**. It contains no API key, prompt or response. It proves only a local adapter observed a response, not provider identity, upstream routing or amount billed.

### Pinned read-only endpoints

| Owner-selected provider | Fixed GET `/models` endpoint |
|---|---|
| OpenRouter | `https://openrouter.ai/api/v1/models` |
| DeepSeek | `https://api.deepseek.com/models` |
| Local 9Router | `http://127.0.0.1:20128/v1/models` |

All are determined by VARYN source, not a model or user-supplied URL. Headers contain an environment-sourced bearer token; redirects are disabled. For 9Router localhost, system HTTP proxy inheritance is explicitly disabled to avoid sending loopback tokens to a proxy. For HTTPS providers, the owner must trust their OS network/proxy configuration. The API list is bounded to 3 MiB, up to 10,000 raw elements and 60 displayed sanitized IDs; no prices, free-status claims, tool instructions, memory or chat content are accepted into the registry.

**No background polling**, no automatic discovery, and at most **one attempted discovery per opened dialog**. Close/reopen requires separate new review to try again. A closed dialog cannot cancel a GET already sent, but its returned data is discarded. The raw response, key and request authentication header are not persisted by VARYN.

## New code and tests

- `varyn/model_discovery.py`: fixed host read-only GET wire, no redirect, local proxy bypass, bounded and sanitized ID-only parser, fresh owner permission/key gates, no retry and explicit false authority flags.
- `varyn/model_catalog_window.py`: native Tk scrollable, owner-reviewed single GET UI, worker-thread response and queued GUI updates, closed-window cleanup and untrusted ID staging; no pricing auto-promotion.
- `varyn/model_control_center.py`: new visible catalog button, edit lock while catalog is open, clear child on close. The older 17S-39/40 provider gateway remains separately gated for actual chat completions.
- `tests/test_model_discovery.py`: malformed/oversized/malicious catalog cases, duplicate/truncated models, missing credentials/permission, rejected fake pricing, **real localhost HTTP GET** mock with deliberately broken system `HTTP_PROXY`; never a remote API key/provider.
- `tests/test_model_catalog_tk.py`: native Windows Tk denied and approved fixture, exact GET approval, one request only, untrusted ID staging resets prices/permissions, offline desktop and 9Router upstream refusal; all requests injected **synthetic** fake-data transport.
- `varyn/frozen_model_center_smoke.py`: real **PyInstaller-frozen** Tk startup also verifies the new catalog exists, starts network OFF and refuses GET even when the dialog toggle is ON, because smoke-only desktop capability remains OFF.
- CI: explicit unit regression and Windows native Tk stages plus complete Ubuntu/Windows regressions and unsigned frozen EXE smoke + four historical independent frozen DPAPI processes.

### Evidence status

This checkpoint's CI **must** be verified at exact final HEAD before calling it complete. A local test/mock server does **not** attest actual OpenRouter, DeepSeek or 9Router connectivity, a provider billing event or a signed-in user account. A real provider GET requires the owner to run the EXE with an OS credential on the owner's own Windows PC. No real API credentials were read or transmitted by GitHub CI.

Original **Option C** automatic two-way history and memory synchronization **inside the three official consumer apps** remains **BLOCKED/unverified** and separate from provider API model discovery. PR #1 remains OPEN/DRAFT and `main` must not change without explicit owner approval.

Official endpoint references (reviewed November 6, 2026):
- DeepSeek: https://api-docs.deepseek.com/api/list-models/
- OpenRouter: https://openrouter.ai/docs/api/api-reference/models/get-models
- 9Router: https://github.com/decolua/9router/blob/master/README.md
