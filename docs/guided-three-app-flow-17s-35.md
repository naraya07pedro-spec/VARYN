# VARYN 17S-35 | Guided ChatGPT → Claude → Gemini manual collaboration

2026-11-05. This adds a concrete **three-app sequential task workflow** to the existing official-consumer-app manual relay workbench. Opsi C remains targeted; this is **not** automatic signed-in account history or memory synchronization.

## Product behavior
The workbench already allowed three manual relay hops but required owners to choose each provider and author each next task. This created avoidable wrong-provider and skipped-review risks. 17S-35 provides three new buttons:

- `Start three-app guided review` validates a bounded (≤650 characters) owner-authored `SYNTHETIC:` task with heuristic credential checks, requires the existing relay idle, selects **ChatGPT** and marks the first stage ready. No browsing/copy.
- `Prepare next app after reviewed reply` is disabled by logic until the **existing exact outbound packet approval**, local copy confirmation, **exact bound pasted reply review and acceptance** occurred. It then fills a locally prepared **Claude critique** or **Gemini synthesis** task and selects the target. It never auto-launches the website, contacts a model, writes to clipboard, or treats the pasted reply as verified.
- `Discard guided flow and relay RAM` explicitly clears both bounded state machines and the editable pasted-reply box. It does not erase OS clipboard contents or project memory notes.

The first Claude task asks it to critically assess ChatGPT's unverified reply and **include a summary** for the next reviewer. Gemini then synthesizes Claude's last locally reviewed reply. As the underlying relay retains only the previous pasted reply, **the first response is NOT independently preserved in the third packet** unless the Claude reply summarizes it. This limitation must be disclosed: an owner can check fidelity and decide to stop.

The `GuidedThreeAppFlow` logic has `idle → ready → awaiting_reply → ready_next → ready` with `completed` only after the third locally reviewed pasteback. The guided flow does not bypass the old TTL, per-packet consent, clipboard review, bound-return receipt, three-hop limit, and local project opt-in. Attempting an incorrect provider, skipped stage, missing review, active old relay, or invalid synthetic task fails closed. The owner can always discard and revert to the original manual workflow.

## Threat boundaries and tests
- No browser automation, scraping, cookie access, consumer app API use, hidden provider request, sensitive file read, account history import, auto-sync, or persisting remote replies. `provider_reply_origin_verified=False`; `consumer_history_sync_verified=False` always.
- Tests: `tests/test_guided_trio_flow.py` state-machine contracts including all three reviewed stages, denied wrong-provider and bypass checks; `tests/test_guided_trio_flow_tk.py` Windows actual Tk controls invoke the original modal reviews with mocked owner decisions, asserting three local packet copies and zero provider requests.
- Workflow: dedicated both-OS state machine suite, Windows native Tk integration, existing full suite and portable frozen Tk/DPAPI build gates unchanged.
- Actual owner device, human browser actions, full transcript fidelity, Gemini provider-side import availability, and true automatic bidirectional memory synchronization remain unverified.

Stage is **implemented** only when committed to the existing feature branch and **CI-verified** only if both OSes and final exact-HEAD portable artifact succeed. PR #1 stays DRAFT; `main` untouched.

## Exact guided task binding (red-team revision)
After the stage is prepared, copying is refused if the workbench task text was edited. The original outbound owner-review path remains mandatory. Editing the task requires discarding guided mode and restarting. Pure-controller and hosted Windows real-Tk tests cover an edited synthetic task on the correct provider, preventing a misleading guided-stage success claim.
