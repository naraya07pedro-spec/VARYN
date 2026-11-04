# VARYN 17S-3 | Nonblocking public tool execution and revocation

Date: 2026-11-04. Scope: next bounded Tool Integration & Permission System milestone on the existing draft PR. **Not** universal tool permissions, OS authentication, or consumer-app history synchronization.

## Motivation and implementation

The 17S-2 public GitHub metadata GET ran synchronously on the Tkinter UI thread; while HTTP blocked for up to five seconds, permission changes and local dismissal could not be handled reliably. The gateway also held its reentrant lock across the external fetch. This was a real responsiveness and consent-revocation gap, not merely a missing cosmetic button.

- `varyn/public_github_tool.py` now reserves its one-use approval and local request budget while holding its internal lock, then **releases the lock during transport**. An epoch counter invalidates all pending approvals and all in-flight results on explicit `revoke_active()` and `close()`. A result returned from HTTP after invalidation is dropped, never delivered. Errors are generic and do not reveal exception bodies. Remote data from both genuine and injected fetchers are revalidated against a complete read-only metadata schema and reduced to approved fields.
- `varyn/public_tool_worker.py` owns at most one worker thread and one bounded result slot. On the trusted Tk thread, `submit()` returns immediately; the worker executes the already-approved gateway request, and the Tk thread calls `poll()` on a timer. Only the Tk thread appends results. A cancellation or closed UI suppresses results without blocking the UI on a network join.
- `varyn/desktop.py` uses the new worker for the public GitHub tool. The GitHub-specific consent checkbox remains independent of model-provider network consent. Turning it off revokes the gateway's pending and in-flight result authority. A new explicit **Hide/cancel public GitHub tool result** button suppresses output for that request. Closing with a public request still in flight warns that an already-started GET may continue; closing never waits for that request.
- `tests/test_public_tool_worker.py` covers blocked transport with responsive submit/revoke, invalidation while HTTP is running, no parallel replacement while a cancelled request is unfinished, revocation before worker dispatch, nonblocking close, safe re-use after completion, generic error handling, and strict untrusted data revalidation.
- Existing `tests/test_public_github_tool.py` now checks the asynchronous desktop callback. `tests/test_public_github_tool_tk.py` invokes hosted Windows Tk widgets with mocked network fetches, including disabling GitHub consent while a mocked GET is in flight. `.github/workflows/memory-checks.yml` adds explicit 17S-3 regression steps on Windows and Ubuntu.

## Example UX

1. Leave the public GitHub network checkbox OFF. Paste the existing public repo metadata JSON request and click the dedicated review button. No request is sent.
2. Enable the *GitHub-specific* checkbox, review the exact repository and fixed GitHub endpoint, and approve. The UI continues responding while the authorized read-only GET runs on a worker.
3. If permission is revoked or **Hide/cancel** is clicked while the request is running, the local result is suppressed; a newer request cannot start before the old worker stops.
4. If the app is closed, the worker cannot update Tk or reinsert results. The process may still finish an already-sent GET; this is not guaranteed HTTP-level cancellation.

## Explicit limitations and threat model

- No OS account authentication, Windows security token binding, separate sandbox process, personal file access, GitHub private account access, repository write operations, or provider API keys have been added.
- `approved=True` and the permission checkbox remain trusted in-process UI assertions. Model output cannot authenticate a user. Same-process malicious code could bypass Python-level gates. Do not process client secrets.
- A network request already accepted by transport cannot be withdrawn or unsent. Permission revocation invalidates its pending and delivered **local result**, not necessarily the remote HTTP request itself.
- Network CI is **mocked**, including the hosted Windows Tk regression. Real connectivity, native Windows owner-device acceptance, proxy/DNS policy, real account identity and resource behavior on the owner's laptop have **not** been verified.
- The original public GitHub metadata tool still only reads public metadata. No arbitrary website browsing, dynamic URLs, search or autonomous planner dispatch is authorized.
- The user's fixed Option C target for automatic **two-way synchronization of official consumer ChatGPT/Claude/Gemini apps** remains externally blocked. This implementation is not a substitute.

## Acceptance

The code and docs must be committed to the existing draft feature branch. Windows and Ubuntu GitHub Actions must report SUCCESS on the exact **final HEAD SHA**. Count tests and skips from actual CI logs. Report earlier red commits if they uncovered failures; do not claim product acceptance or authenticated security boundaries from synthetic tests.

Next: formal OS/user identity and process isolation design; ensure launch-time permissions and revocation survive harder failure modes, then move toward explicitly scoped, useful integrations and tested owner-device workflows.