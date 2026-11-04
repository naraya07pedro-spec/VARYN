# Checkpoint 17J: Real Tkinter widget command smoke, synthetic-only

**Date:** 2026-11-04 (Asia/Jakarta)
**PR:** #1 draft on feat/local-memory-prototype-20261103, without merging main.
**Purpose:** Progress from headless Python method testing to exercising the actual Tk widget tree and registered button commands. DO NOT mistake synthetic programmatic invocation for a real human click, Windows login/consent authentication, or physical owner-PC acceptance.

## What changed

The new varyn/tk_widget_smoke.py loads the real VarynDesktop (tk.Tk), enumerates its actual nested ttk.Button objects, and calls the real Button.invoke() callbacks for **Create & grant VARYN demo folder**, **Inspect test-folder count** and **Revoke test-folder grant**.

Safety constraints in the test:
- DesktopController is instantiated with allow_live_providers=False; fake model is selected and network consent remains off.
- NativeToolRequestClient is temporarily replaced by a real but allow_network=False instance. No paid provider, browser, account, export, clipboard, arbitrary local file or network tool is used.
- tkinter.messagebox.askyesno is replaced *inside the smoke test* with the deterministic synthetic responses NO, YES, YES. This simulates a user decision; it is not actual user consent or a claim about the owner.
- The desktop may only construct its fixed two-file VARYN-owned SyntheticFixture. No user-specified root, Documents, cloud drive or real personal file is accepted.
- The test checks that refusing consent creates no grant; approving produces one local grant; pressing the Tk Inspect button displays a count of two; no folder path, sample filename or file text is displayed in the transcript; pressing Revoke destroys the disposable fixture and denies the previous grant.
- A third Create invokes a temporary one-second grant (only in this synthetic smoke). Without clicking or polling the permission, the test waits for actual timer-triggered fixture deletion. It then shuts the desktop window, opens a fresh real Tk window, and verifies no old active grant is restored.
- The report contains fixed generic booleans only and never prints tracebacks, file paths, sample contents, account data or raw exception messages. GUI is hidden/withdrawn once created to limit visual disruption. This is still REAL Tk widget callback wiring, not screenshot visual QA and not OS-level mouse-event automation.

## CI and local commands

Run from inspected VARYN repository with Python 3.10+, Tkinter and an active graphical session, in an ordinary Windows user terminal (NO Administrator):

    py -3 -m varyn.tk_widget_smoke --synthetic-only --require-display --json

GitHub Windows runner executes the exact command as a mandatory CI step, *in addition to* the main 17J test module:

    python -m unittest discover -s tests -p "test_tk_widget_smoke.py" -v

Ubuntu runners run the headless module tests only. Missing GUI support is explicitly reported as **unavailable_no_graphical_session** (non-zero exit) rather than falsely passing or silently skipping. If Windows CI lacks usable Tk display, CI must fail or report the unsupported environment; do not claim UI acceptance.

The report's fields ALWAYS say:
- human_mouse_clicks_performed: false
- human_consent_obtained: false
- owner_physical_pc_tested: false
- official_provider_connected: false
- network_requests_by_test: 0

A status of passed means *only* that the real local Tk button command wiring and synthetic permissions exercised by this test behaved as specified. A person still needs to visually inspect the real desktop on the owner's machine and complete the independent owner-observed checklist from 17I.

## Failure and remaining limitations

- A Tk session may be unavailable (e.g., no DISPLAY, inaccessible Windows desktop, locked session). The correct outcome is unavailable, NOT PASS.
- A native Windows API can behave differently on a real owner laptop with antivirus, cloud placeholders, sleep/wake and restricted TEMP; hosted CI does not establish owner-hardware acceptance.
- Button.invoke invokes the same Tcl/Tk button callback registered by the program, but it is not a real cursor click, keyboard accessibility test, display rendering test, or human approval of a modal.
- No OS process sandbox or Windows ACL authentication is established. Permissions remain experimental trusted-host in-process objects scoped to synthetic data.
- Timer expiry and filesystem deletion remain best effort; power loss/forced termination can leave harmless generated fixtures.
- Official consumer app ChatGPT/Claude/Gemini read/write two-way synchronization is still blocked pending concrete provider READ+WRITE account-level evidence and approval, as enforced by 17I's seven gates per application. No actual official-app sync is implemented or tested here.

## Evidence and next gate

See docs/progress-log.md for the exact implementation SHA and final Windows/Ubuntu CI outcome. Next meaningful gate after successful hosted Tk test is executing this command on the owner's normal Windows account, plus manual UI and usability checks; preserve separate provenance of hosted CI, local automated Tk and self-reported human observations.

**Verdict:** a substantial step beyond method-only UI tests when the real Tk step executes. Not a substitute for genuine local hardware GUI acceptance or the user-selected Option C requirements.
