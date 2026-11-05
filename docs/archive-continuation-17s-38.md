# VARYN 17S-38 | Resume prior synthetic archive as FRESH, separately approved task

Date: 2026-11-05. The 17S-37 Windows DPAPI archive stored three fully locally reviewed SYNTHETIC app replies but was read-only. The user could inspect it after a restart but could not carry a selected piece of context into a subsequent new manual handoff. 17S-38 closes that workflow gap without replaying old authority.

## User-facing execution
1. Start with **idle** workbench and no pending/previous relay or pasted reply. Choose archived stage 1 (ChatGPT), stage 2 (Claude) or stage 3 (Gemini). Selection labels are **unverified owner claims** from the archive.
2. Click `17S-38 | Select encrypted archive excerpt (review)`, choose an encrypted owner-owned `.varyn-archive` file, and review the **exact** locally decrypted, bounded synthetic excerpt before a separate Stage approval. The selected file must match strict 17S-37 schema and each recorded local SHA256 receipt. Reentrant state changes, source-stage changes, unsafe archives and active relays refuse staging.
3. On approval, VARYN writes an explicit safe `SYNTHETIC:` continuation proposal into the **editable task field**. It does **NOT** contact any provider or clipboard. It creates a frozen in-RAM `ArchivedExcerptSelection` with stage, locally claimed provider, archive SHA256, original local reply digest, length and `TRUNCATED` marker.
4. `Include reviewed old excerpt in NEXT fresh manual packet` defaults **OFF**, even after the initial excerpt review. Only if the owner separately checks it does `OfficialManualRelay.prepare(..., archived_excerpt=...)` embed a precisely source-labeled and quoted `UNTRUSTED DATA` section in the **new** packet for the owner-chosen official destination. The old 3600-character cap and exact original owner clipboard review + TTL remain; copying requires another explicit owner approval.
5. After a successful fresh handoff, discard/close, or switching to guided mode, the staged archive selection is erased from RAM and the inclusion checkbox returns OFF. Any attempt to inject the old excerpt mid-relay, while running guided three-app flow, after changing the selected source, or using non-typed forged context fails closed.

## Threat boundaries
The old 17S-37 archive stays read-only. Selecting an excerpt **never** restores prior approval, browser session, account credentials, relay hop counter, previous external reply, or provider history/memory state. Local hash matching only verifies self-consistency of owner-pasted unverified content, not signed-in ChatGPT, Claude or Gemini provenance. This cannot bypass genuine provider permissions and is NOT automatic bidirectional native consumer-app history sync. The archive file is bound to the Windows OS profile; selection/excerpts are transient RAM, not automatically saved. The optional 480-character excerpt may omit relevant context and can contain adversarial text; it is quoted and labeled as untrusted data, and the owner must approve the exact outgoing packet.

## Evidence
- `varyn/archive_continuation.py`: immutable, tightly scoped archive context selection and stable synthetic continuation task.
- `varyn/official_manual_relay.py` and `varyn/desktop.py`: new explicitly selected archived excerpt is supported only for **fresh** manual handoff; never compatible with active guided history.
- `varyn/official_relay_workbench.py`: stage chooser, decrypted-file review, default-OFF checkbox, exact final owner copy review, discard/close cleanup.
- `tests/test_archive_continuation.py`: all three stages, truncated excerpt, forbidden flags, forged selections, denied fresh copy and mid-relay refusal.
- `tests/test_archive_continuation_tk.py`: hosted Windows Tk full flow using actual Windows DPAPI, denied/approved archive selection, default-OFF handling, wrong stage denial, second denied/approved outbound clipboard review, no API requests and stale state cleanup.
- CI runs both suites, full Windows/Ubuntu regressions and frozen Windows portable GUI/DPAPI restart package gates on exact commit.

**Provenance/acceptance:** no owner-device human clicks or real app accounts are verified. Opsi C target remains native official-app eventual bidirectional sync, not the API-only route. PR #1 remains DRAFT and `main` untouched.
