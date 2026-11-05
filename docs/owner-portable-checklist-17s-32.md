# VARYN 17S-32 | Owner PC checklist directly in the portable workbench

Date: 2026-11-05. Scope: remove the Python terminal requirement for user-entered real-device acceptance observations. No provider integration or secret parsing is added.

## Concrete product improvement
The 17S-29 standalone unsigned Windows x64 portable EXE already starts a focused 17S-28 workbench without any separately installed Python. However, completing the original manual owner report still needed a different terminal running `varyn.owner_pilot_launcher`. This stage puts the existing **seven official-app relay steps and three project-note steps** into a single scrollable Tk child window of the workbench.

Click `17S-32 | Owner PC acceptance checklist`. Each check starts `not_checked` and can be set to `pass`, `fail`, or `not_checked` only. `Review fixed self-report` displays JSON assembled solely from ten allowlisted fixed choices via the existing `combined_owner_report` logic. A selection change destroys the previous review. `Copy reviewed report (separate consent)` prompts for an independent YES and revalidates the reviewed answer snapshot after that modal. Refusal or stale review does not overwrite clipboard. Closing destroys local self-report state without saving/uploading. The OS clipboard can retain explicitly approved copies after closing.

No free-text responses, account names, chats, local machine ID, file paths, personal history or credentials are collected. No browser inspection, network request, provider API call or memory persistence is performed by this checklist. The parent relay's own consent gates remain intact and separate.

## Critical evidence boundary
The report is **owner-entered self-report**, not independent proof of physical interaction. Scripted Tk `Button.invoke` and fake answers can also generate the JSON; that is intentionally not mistaken for human attestation. Even an all-`pass` checklist **does not prove** remote browser delivery, authentic ChatGPT/Claude/Gemini origin, read/write account history permissions, safe private file access or automatic two-way synchronization. `varyn.option_c_gate` stays blocked.

## Tests
- `tests/test_owner_pilot_checklist_gui.py` validates defaults, all-pass cannot elevate authority, invalid types/extra user text rejected.
- Hosted Windows native Tk test exercises the workbench button, singleton window, initial no-copy, rejected copy, invalidated stale preview, a separate consent for fixed JSON clipboard copy, and RAM report discard. No real owner-PC or official-app login is tested.
- Cross-platform full suite, hosted native Windows Tk tests, and actual unsigned portable frozen-GUI smoke must pass on the **exact final branch commit**. ZIP artifact existence on the same run must be confirmed. This document is not an assertion those checks have already passed.

## Owner workflow
1. On ordinary, non-admin Windows, unpack the full `varyn-windows-portable` artifact and open `VARYN-Portable.exe`. Never bypass Defender or SmartScreen for this unsigned prototype.
2. In the automatically opened workbench, click the 17S-32 checklist. Use **only** fake `SYNTHETIC:` task content.
3. Perform the first and second official-app manual transfer, denial and return steps in the actual browser, then project-note conflict/opt-in/discard tests. Mark observed outcomes only. Do not assert pass for untested steps.
4. Review the fixed JSON, separately approve copying, and paste it into the project conversation if you want to share it. VARYN itself does not upload the report.
5. Never upload private history/ZIPs to VARYN during this pilot. Manual official Gemini import remains a distinct provider-side process with its own privacy terms.

## Release gate
Stage is implementation-complete only once same-HEAD Windows+Ubuntu CI and portable artifact pass. Real owner-PC acceptance is **PENDING** until the owner performs it. This milestone does not resolve the provider-side limitations of Option C. Keep PR #1 DRAFT and do not change `main`.
