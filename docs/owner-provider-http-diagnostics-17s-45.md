# VARYN 17S-45 | Safe HTTP failure diagnostics for owner-PC model pilot

Date: 2026-11-06 WIB. This checkpoint improves the **single live inference attempt** feedback. It does NOT authenticate any owner account, connect official consumer-app history, or use an actual API key.

## Problem fixed

Previously the Model Control Center reported any failed or denied inference as a generic provider failure. It was impossible for the owner to distinguish an authentication problem from missing credit, model inaccessibility, rate limiting or provider downtime. Blindly retrying can create repeated requests or uncertain charges.

Now the fixed-endpoint chat transport intercepts HTTP error status codes without reading, logging, storing or propagating the remote response body, headers, reason phrase, or original exception. It raises only a locally constructed, finite-category SafeProviderHTTPError. The GUI worker sends the category across its queue and displays a static hint.

Categories: HTTP 400 bad request; 401 authentication; 402 billing; 403 access denied; 404 missing model/endpoint; 408 timeout; 409 conflict; 422 invalid parameters; 429 rate-limited; 5xx server failure; other statuses remain generic. These describe the observed HTTP response and may come from an intermediary or gateway. They do NOT prove the real provider account state or its billing.

## Safety invariants

- Normal owner review, explicit one-request permission, price estimate review, exact route selection and network OFF by default remain unchanged.
- No retries or fallback introduced. Failed/uncertain attempts retain their local request reservation; actual billing remains unknown.
- Never print or save the provider's original HTTP error body, headers, reason phrase, credentials, cookies, prompts or traceback in the new diagnostic surface.
- A successful inference is still not proof of native consumer ChatGPT/Claude/Gemini account history and memory sync.
- A 401/403/402 may indicate an intermediary, payment or permission problem. Do not reflexively retry; check the provider's official console locally.

## Tests and status

New tests in tests/test_provider_http_diagnostics.py cover bounded status mapping, sensitive-data suppression, a real **localhost HTTP 429 response**, exactly one request/no retry, and sanitized GUI-worker propagation. These are SYNTHETIC tests and use no external account.

At commit time, CI and frozen portable build must be verified on the exact HEAD before calling this checkpoint green. Real owner-PC EXE acceptance, one real provider-model inference and actual charging/credits are still pending.

## Owner acceptance after downloading the exact latest artifact

First check the ZIP SHA-256 against GitHub Actions, extract the full folder and run Start-VARYN-OwnerPilot.ps1 -VerifyOnly from a normal PowerShell session. Launch offline and test FAKE as previously documented. When ready and only with a genuine local API key, launch with -Provider openrouter or -Provider deepseek, Discover model IDs, inspect the actual price and entitlement in the provider console, register a reviewed price, then approve exactly ONE SYNTHETIC: inference.

If the GUI shows HTTP 401, 402, 403, 404 or 429, do not immediately retry. Inspect account permissions, pricing, model ID and rate limits locally. Report only provider, *category*, whether a single request was attempted, and whether an answer appeared. Never upload a key, raw headers or personal prompts.

**Authority:** PR #1 stays OPEN/DRAFT. Default main branch unchanged. Original Option C native automatic two-way consumer-app sync is still unverified/blocked.
