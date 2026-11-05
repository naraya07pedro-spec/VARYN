# VARYN 17S-28 | Focused official consumer-app manual workbench

Date: 2026-11-05. PR #1 stays **OPEN / DRAFT**, base `main` unchanged. This is an **experimental, user-mediated** local workflow, not Option C automatic bidirectional consumer app history/memory synchronization. Final CI must be checked on this exact documentation HEAD.

## Product gap and implementation verdict

Stages 17S-22 through 17S-27 created reviewed clipboard handoff, unverified reply review, temporary project context, a Windows launch ZIP and callback-only local audit. However, the desktop has many unrelated controls scattered through a long scroll view. Testing the official-app workflow required repeatedly replacing the original Message field, with the risk of losing locally typed work.

17S-28 adds a **single scrollable owner-facing workbench** to guide the core task without changing the original main Message field. It reuses the previously tested real consent gates rather than creating a second, unreviewed clipboard or browser path.

## Implemented code and UI

- `varyn/official_relay_workbench.py`: an actual Tk `Toplevel`, 680x630 initially, minimum 510x430, scrolling content. The top of the parent desktop now exposes `17S-28 | Open official-app relay workbench`. Reopening focuses the existing single workbench instead of duplicating independent copies; closing the workbench removes only its own editors. The shared relay's temporary RAM state remains until explicit Discard or parent desktop close.
- Workflow: **(1)** select pinned official app and separately approve opening its homepage; **(2)** enter a harmless `SYNTHETIC:` task and review a complete immutable clipboard packet; **(3)** manually paste a short external reply into a separate input and explicitly review it as an **unverified** source; **(4)** optionally type/review a `SYNTHETIC:` project note, inspect any conflict and turn on sharing for the next separately reviewed packet. Both relay and working context have separate Discard controls in the workbench.
- The workbench has its own task, reply and note editors, project/topic labels and opt-in checkbox (OFF by default). It does **not** overwrite the main desktop Message text; it passes explicit scoped values to existing callbacks. There is no automatic reading of browser tabs, clipboard, private files, exported account histories, or model-provider credentials.
- `varyn/desktop.py` now accepts optional keyword overrides for existing `_open_selected_official_app`, `_copy_official_app_relay`, `_review_official_app_reply`, and `_review_project_working_note`. No overrides preserve old button behavior. An explicit context-sharing choice must be a real boolean; invalid choices, wrong project or missing approved notes fail closed. It continues to invoke the same exact packet preview, 90-second copy TTL, outbound-bound reply receipt review, project conflict review, opt-in context selection and local callback audit.
- The workbench refuses unsuitably formatted task/note inputs before any parent callback: task must start with `SYNTHETIC:` (at most 1,000 chars); note must start with `SYNTHETIC:` (at most 320 chars); return reply must be nonempty, at most 1,600 chars and undergo the existing parent input/preview validation. This is NOT a comprehensive data-loss-prevention scanner. Never type real secrets or private conversations in the prototype.
- A status line derives from local relay state: awaiting manual reply, unverified reply staged, hop limit, note count and next app context sharing state. The label **never** claims remote app delivery, authenticated user login or provider history sync. The workbench itself contains no HTTP client, browser automation, background task or filesystem writes.

## Security and evidence boundaries

- Success in the hosted Windows Tk tests uses programmatic button invocation and mocked browser/prompt approvals. That proves callback wiring and state invariants, **not** actual user action on the owner's Windows machine or browser transport.
- A clipboard packet must still be manually pasted into the *actual official* ChatGPT, Claude or Gemini app. The returned reply is user asserted and unverified; neither receipt digest nor local audit proves its provider origin or correctness.
- The main VARYN model API provider remains independently configurable. During owner pilot keep it `fake`, with VARYN network/provider API consent OFF; the browser may independently communicate with the official site only after user approval.
- The project context is RAM-only and synthetic-only; not encrypted durable private memory. A closed workbench doesn't revoke an active relay; explicit Discard or full desktop close does. OS clipboard text may outlive VARYN.
- The existing `varyn.option_c_gate` must remain **blocked**. This is a UX improvement to manual continuity and cannot satisfy provider-sanctioned authenticated consumer-app bidirectional conversation/history/memory read/write.

## Verification

- Portable callback regression: `tests/test_official_manual_relay_desktop.py` checks explicit workbench task, target and project overrides without overwriting main editor; invalid opt-in/other-project data cannot silently copy.
- Native Windows workbench: `tests/test_official_relay_workbench_tk.py` invokes actual Tk widgets to exercise one-window sequence, real parent method gating (owner dialogs mocked), correct first-to-second official app handoff via local clipboard, unverified return, project-note default-off versus explicit inclusion, independent discard, singleton behavior and invalid synthetic input refusal. No remote app browser or human click is independently observed.
- `.github/workflows/memory-checks.yml` has explicit 17S-28 portable checks and a Windows-only native Tk early gate, plus existing full Linux/Windows suite, ZIP content integrity and publication.
- Final exact-HEAD run URL, SHA, discovered test counts, artifact ID and any red-to-green fixes must be recorded on PR #1. Tests cannot substitute for user acceptance.
- Run on the owner's Windows PC from the latest successful source ZIP: extract `VARYN`, double-click `Try-VARYN-Official-Apps.cmd` as normal non-admin user with Python+Tkinter already installed, click the prominent `17S-28 | Open official-app relay workbench` button. Complete the synthetic first-to-second official-app pilot and optionally use the 17S-27 local callback audit. The owner should report actual UI/blockers rather than blindly answering yes.

## Next meaningful priority

Physical owner-device usability and two actual consumer-app test sessions are still pending. Independent source-backed verification of official provider consumer-history **read AND write** authorization remains the decisive Option C gate. Continue to avoid unapproved cookie extraction, private file access, browser scraping and API-only substitution.
