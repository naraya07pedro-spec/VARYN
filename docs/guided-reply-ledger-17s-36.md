# VARYN 17S-36 | Complete local three-app reply ledger and excerpt handoffs

Date: 2026-11-05. This stage fixes the critical limitation of 17S-35: the original ChatGPT reply was lost from Gemini's next packet when the Claude reply replaced the relay's previous-response slot. Depending on Claude to summarize it was insufficient.

## Functional implementation
`GuidedReplyLedger` stores three exact, locally reviewed, user-pasted `SYNTHETIC:` replies in RAM with a fixed stage/provider order, outbound request and digests, and locally chained return receipt digests. App names are **claimed by the person pasting text**, not externally authenticated. Local hashes prove consistency with locally reviewed text, not remote delivery.

A new `17S-36 | View complete locally reviewed replies (RAM)` button opens a read-only Tk window for all full replies and digests. Local discard and workbench close clear the ledger and the viewer; no disk or automatic clipboard export occurs.

`GuidedHistorySelection` is an explicitly typed prior-stage selection that injects stage-specific, source-labeled quoted excerpts into the existing `OfficialManualRelay.prepare` packet. Claude receives a labeled ChatGPT excerpt; Gemini receives separate **ChatGPT and Claude excerpts**, each capped at 540 characters. `TRUNCATED` marks any incomplete excerpts with the original length. The legacy last-response block is skipped only when this selection is provided, preventing duplication. The existing 3600-character maximum packet size remains; oversized packets fail closed. Exact user review, 90-second TTL, three-hop limit, clipboard consent and manual official-app paste all remain required.

## Limits
Full stage replies remain in local RAM only and are discarded on process close. Excerpts may omit important details. Guided receipts must not be confused with authenticated ChatGPT/Claude/Gemini account origins. No automatic app memory import/export, bidirectional history sync, remote provider API, browser automation, secret access, external upload, or persistent autonomous execution is added.

## Verifiable test gates
`tests/test_guided_reply_ledger.py` validates three-stage full text retention, two independently labeled Gemini excerpts, local digest mismatch refusal, wrong source/order, nonsynthetic and obvious secret refusal, forged history type refusal, and reset/discard. Existing pure guided tests and Windows hosted actual Tk guided tests are updated for receipt requirements, stage view and cleanup. Dedicated CI plus full Windows/Ubuntu suite and frozen Windows portable GUI/DPAPI smoke must pass at exact final SHA.

Actual owner PC and signed-in official-app/browser behavior have not been observed. Preserve Option C target, keep PR #1 DRAFT and `main` unchanged.
