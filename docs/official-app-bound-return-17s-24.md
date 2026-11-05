# VARYN 17S-24 | Outbound-bound return receipts for manual official-app continuity

Date: 2026-11-05. Status when written: **implemented; exact final commit CI must be checked**. PR #1 stays OPEN/DRAFT; `main` unchanged. No browser login, scraping, provider account access, private-file read or automatic ChatGPT/Claude/Gemini history synchronization.

## Why this is a necessary product step

17S-22/23 let a user manually move a task to an actual consumer app and paste the answer back. Previously the desktop reviewed pasted text but did **not** bind the approval to the exact preceding outbound request. A nested Tk modal/close/discard could invalidate the handoff while an older approval dialog was still open. Additionally, the return metadata needed a well-defined one-shot cleanup contract to avoid reusing discarded context.

17S-24 adds a bounded **local chain of custody** for user-mediated information transfer. This is local state integrity, **not proof of external provider identity or a remote delivery receipt**.

## Implemented

- `ManualReturnPreview` is an immutable local object containing the **claimed** official app provider, the exact outgoing VARYN request ID and digest, a SHA-256 digest computed over that outgoing binding plus the user-pasted text, the exact bounded reply text, and a 90-second approval expiry. `origin_verified=False` is permanent and explicit.
- `OfficialManualRelay.begin_return_review(reply)` is permitted only when **one** successful local clipboard copy is awaiting an answer. It prepares exactly one live return review, without opening a browser or reading a clipboard. Any duplicate simultaneous return review is denied.
- `OfficialManualRelay.finish_return_review(preview, approved=...) ` accepts **only the same live object** and the same still-current outbound request/provider/digest. Replacements, stale objects, changing provider, expired approvals, replay, and revoke while a modal is open fail closed. Denial retains the outgoing request for a separately reviewed new reply; approval burns the reviewed token and stages bounded reference text in RAM.
- On acceptance, VARYN computes a **local SHA-256 chain digest** over prior local chain metadata and the outgoing/reply digests. `last_return_receipt()` returns metadata including claimed provider, local outbound request ID/digest, return digest and chain digest, without transcript content or remote authentication claims. The explicit *next* user-reviewed packet may include the local receipt identifier and chained digest alongside the quoted, unverified reply. **Hashing does not authenticate a remote provider** and the chain is not a cryptographic signature or tamper-evident persistent store.
- `varyn/desktop.py` now shows the outgoing request ID, claimed provider, unverified-source warning, exact return digest, and full text in the scrollable modal. It binds the user's approve/decline to the exact return-preview object instead of an unbound `reviewed=True` call.
- `discard_pending()`, `reset()`, desktop shutdown and nested cancellation clear the pending return token, request binding, last receipt and local chain metadata. It does **not** forcibly wipe Python heap pages, external app chat logs, or OS clipboard. Any explicit lower-level `record_pasted_reply` path used by legacy unit tests must not claim a reviewed `return_receipt`, and it cannot bypass an active exact-return UI review.

## Verification and limits

- New `tests/test_official_return_receipt.py` exercises accepted one-shot return, denied retry, expiry, forged/fresh-copy previews, nested revocation, wrong provider, unverified origin, next-hop transfer, no provider HTTP and full receipt cleanup. Existing `tests/test_official_manual_relay_desktop.py` adds desktop nested cancel, exact outbound binding and expiry regressions.
- Hosted Windows Tk `tests/test_official_manual_relay_tk.py` checks outgoing ID, digest, content and unverified warning are passed into the actual modal flow, **without a human click**.
- The early CI gates for this stage are in `.github/workflows/memory-checks.yml`.
- Red evidence: initial receipt test exposed metadata surviving reset on CI run [#41987690333](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41987690333). The reset/discard cleanup was corrected in commit `37dc48f6e9cbeb9908777d185bf5d65dc0d25501`. A green exact-final-HEAD Windows/Ubuntu CI run is still required and must be documented on PR #1.
- The actual manual two-app owner-PC test in `docs/official-app-owner-pilot-17s-23.md` remains **NOT independently performed** here. Desktop tests use synthetic inputs and mocked provider/browser actions.

## Remaining high-priority blockers

1. Local PC acceptance with a normal Windows desktop session and two genuine official AI app accounts, using harmless sample data and explicit clicks.
2. Independent verification of documented official consumer-app history **read and write** interfaces, account scopes and terms for the three providers, plus stable change detection and conflict/revocation semantics. The existing Option C proof gate remains BLOCKED.
3. Real private data, encrypted durable shared memory, and production AppContainer security still require separate evidence. Do not treat RAM receipts or SHA-256 as secure durable provenance.

This change makes manual cross-app continuity **less error-prone**, but cannot substitute for automatic, authenticated, provider-sanctioned bidirectional history/memory sync.
