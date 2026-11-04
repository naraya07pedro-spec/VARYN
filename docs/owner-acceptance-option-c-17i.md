# Checkpoint 17I: Owner-observed Windows GUI acceptance and Option C proof gates

**Date:** 2026-11-04 (Asia/Jakarta)
**Branch:** feat/local-memory-prototype-20261103, draft PR #1
**User requirement:** Continue using the official ChatGPT, Claude and Gemini consumer applications, with future automatic bidirectional cross-app conversation/context sync (Option C). Do NOT relabel manual import, developer model APIs or VARYN-only chats as completion.

## 1. What 17I actually implements

The owner now has an optional, local-only, bounded GUI observation workflow. The source ZIP contains a second launcher, **Record-VARYN-GUI-Checks.cmd**, separate from the pre-existing **Verify-VARYN-Synthetic.cmd**. It runs the existing safe synthetic self-test and prompts the owner to answer six fixed yes/no/skip questions after personally using VARYN's Tk desktop.

The questions cover:
1. Desktop window launched under an ordinary Windows user, with fake provider and network disabled.
2. Refusing consent to the generated demo folder did not create active access.
3. Approving consent then inspecting the temporary example folder showed exactly two sample files.
4. No personal folder, path, filename or file contents were shown in the UI transcript.
5. Explicit revoke blocked a subsequent inspect.
6. Restarting the desktop did not retain the previous temporary grant.

Responses are **strictly bounded**. Exact yes is a reported PASS, no is FAIL, skip/blank/unexpected input is NOT CHECKED. The CLI outputs only predefined status values. No raw answers, identifiers, device model, username, account data, provider credentials, directory path, screenshots or transcripts are collected or persisted. A nonpassing step or unsuccessful synthetic CLI test gives nonzero exit status.

**Critical provenance rule:** Even all six owner-reported PASS responses are labeled **owner_self_reported_pass**, and the report always sets independently_verified_on_owner_pc=false, identity_authenticated=false, and gui_clicks_observed_by_automated_test=false. Nothing here independently observes mouse clicks, validates ownership, cryptographically signs evidence, or certifies data safety. A person could falsely answer yes: this is a checklist and handoff mechanism, not proof of an authenticated user action.

## 2. Safe local procedure (not yet executed on the owner's actual PC)

Use an inspected, trusted VARYN source ZIP on Windows in a normal account, **not Run as Administrator**. Python 3.10+ and Tkinter must be available. No real folders or providers should be used.

- Start with **Verify-VARYN-Synthetic.cmd**. The previous test reports whether generated samples can be listed, their temporary grants automatically expire, and the two harmless files are cleaned up.
- Open VARYN separately, leaving the provider as fake and network permission OFF. Use only the **Create & grant VARYN demo folder** button and its associated Inspect/Revoke actions. Test refuse, approve, inspect, revoke and restart.
- Launch **Record-VARYN-GUI-Checks.cmd** and enter yes, no or skip for each fixed observation. It reruns the synthetic self-test. Nothing is automatically uploaded, and no report file is created.
- For ordinary PowerShell, the equivalent is:

      py -3 -m varyn.owner_acceptance --synthetic-only --interactive

- If reporting results back to the project, share only the sanitized JSON printed at the end. Do NOT share screenshots containing personal data, Windows file paths or API keys. This is optional and does not give ChatGPT access to the user's device.

The human GUI steps remain **unverified here**. GitHub CI is a hosted Windows runner with no actual owner mouse/monitor/antivirus/sleep-state acceptance. The current prototype remains synthetic-only.

## 3. Explicit Option C readiness gates

varyn/option_c_gate.py now exposes **seven separate engineering proof requirements for each official consumer app**:
1. Provider-published programmatic READ for the existing signed-in consumer-app conversation history.
2. Provider-published programmatic WRITE targeting that same consumer account conversation history.
3. Account-level authorization scopes, consent expiry, revocation and authentication.
4. Change capture, stable remote identifiers and revision behavior.
5. Real conflict, tombstone/deletion, retry, deduplication and echo-loop controls.
6. Provider terms/privacy, geographic and account eligibility.
7. End-to-end tested official-app create/update/delete in both directions on a consented account.

The current report for each provider remains **blocked**, with read and write independently **not verified**, all seven requirements still missing verification, and can_dispatch=false. Three-provider Option C readiness is therefore also false. Manual Gemini history import, experimental Claude memory import, developer APIs and an owner GUI self-report do **not** automatically satisfy these gates.

This is an **offline diagnostic**, not an installed connector, a network service, or a workaround that manipulates undocumented browser cookies/consumer APIs. Proof can only be advanced through a separately reviewed implementation with published provider authority and actual account-controlled acceptance. Do not try to bypass provider restrictions with private endpoint scraping.

Offline command:

    py -3 -m varyn.option_c_gate

The command exits 0 when the diagnostic completes, **not** because Option C is available. Its JSON status must be read. An imagined local boolean claim or synthetic test does not unlock dispatch.

## 4. Code, test and CI accountability

- varyn/owner_acceptance.py: bounded interactive owner-reported checklist, separate automated synthetic CLI result, no persistence, sanitized output.
- Record-VARYN-GUI-Checks.cmd: normal-user Windows wrapper, disabled delayed expansion, no admin or network commands.
- varyn/package_desktop.py: source-only ZIP includes the owner checklist launcher; tests verify ZIP excludes secret data.
- varyn/option_c_gate.py: provider-independent proof requirements and non-dispatchable three-app readiness result.
- tests/test_owner_acceptance.py: strict input validation, incomplete/failed/skipped cases, self-report provenance and no raw text output.
- tests/test_option_c_gate.py: independent READ/WRITE gates, no false positive from manual import, isolated mutable outputs and offline CLI.
- tests/test_desktop_packaging.py and tests/test_acceptance_packaging.py: fail closed if required launchers are missing; one-click report has no administrator/network commands.
- .github/workflows/memory-checks.yml: Windows/Ubuntu explicit suites and ZIP contents checks; existing 17G native handle/expiry tests remain.

Exact CI commit and pass/fail evidence are recorded in docs/progress-log.md.

## 5. Remaining blockers and stop conditions

- Physical Windows GUI confirmation on the owner's actual machine remains **pending user execution**; this assistant/CI cannot claim to have done it.
- Current demo read permissions are in-process trusted assertions, not OS account-level ACL isolation or authenticated human consent. Never enable general private files from this checkpoint alone.
- Abrupt shutdown, Windows file locks and delayed Python timers can still leave harmless synthetic sample residues.
- No supported consumer-history read+write interface has been verified for the three official apps. **Option C is NOT delivered.**
- No provider accounts or real files were read, no paid or unconsented requests performed, no state-changing remote action taken, and main remains unchanged.

**Verdict:** 17I improves owner-visible evidence quality and future decision gating, without inventing the one capability VARYN still lacks: authorized automatic bidirectional synchronization of the real official consumer apps.
