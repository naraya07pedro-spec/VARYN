# VARYN 17S-23 | Explicit official-app launch and owner-side two-app continuity pilot

Date: 2026-11-05. Status at writing: **implementation committed, final exact-head CI pending**. VARYN remains experimental. **Option C automatic ChatGPT/Claude/Gemini consumer-app conversation and memory sync is NOT implemented.**

## Why this checkpoint exists

17S-22 introduced user-reviewed, RAM-only clipboard handoff, but a normal user still had to find the intended official app independently; in addition, a long-running copy-review dialog could expire *before* the OS clipboard write. Neither a green hosted Windows UI suite nor a simulated consent answer proves a human completed a handoff on the owner's Windows PC.

17S-23 closes those concrete functional gaps instead of adding another synthetic broker demonstration.

## Shipped code

- `varyn.official_manual_relay.official_destination(provider)` accepts only the exact case-sensitive `chatgpt`, `claude`, `gemini` identifiers and returns pinned homepages `https://chatgpt.com/`, `https://claude.ai/`, `https://gemini.google.com/`. It accepts **no user URL**, no query parameters, no transcript bytes, and no URL derived from model output.
- `varyn.desktop.VarynDesktop` exposes **17S-23 | Open selected official app in browser** in the existing scrollable UI. The user must click it and approve a separate dialog before `webbrowser.open_new_tab` is called. The newly opened official website can make its own network request; VARYN does not send a prompt, token, account history, user name or clipboard contents in that URL and does not authenticate a provider session. A browser-launch return value does **not** prove a logged-in account or successful paste.
- `OfficialManualRelay.preflight_copy(preview)` rechecks the exact trusted, pending, one-time preview identity and 90-second expiry **after owner approval, immediately before clearing or writing OS clipboard**. This fixes the observable case where an expired dialog would otherwise overwrite unrelated clipboard contents. `decide` repeats checks after the clipboard write. There remains a narrow non-atomic gap across OS clipboard mutation and in-memory state update: external clipboard APIs cannot be transactionally combined with an in-RAM relay. On an exception, VARYN fails closed logically, but previously overwritten OS clipboard contents cannot be restored without reading them. Do not copy secrets.
- `varyn.official_relay_pilot` provides a bounded, standalone owner-guided pilot **without network, clipboard, account or disk access**. It asks seven fixed yes/no/skip questions and prints only boolean-equivalent statuses. An all-yes result is explicitly `owner_self_reported_manual_pilot_pass`, **not independent verification**; any skip, refusal, malformed input, or incomplete response prevents that status.
- `.github/workflows/memory-checks.yml` explicitly runs portable URL / TTL / self-report regressions and a hosted Windows native Tk button test. The hosted Windows test mocks the actual browser navigation and owner decision; it cannot prove a real user clicked or the browser rendered.

## How to perform the actual pilot on the owner's PC

Use a normal, non-administrator Windows PowerShell in the already cloned repository. If local changes exist, inspect `git status` and preserve them before switching branches. No elevated permissions, new provider API key, browser cookies or special automation extension is required.

```powershell
git fetch origin
git switch feat/local-memory-prototype-20261103
git pull --ff-only origin feat/local-memory-prototype-20261103
py -3 -m varyn.desktop
```

Open a **second** ordinary PowerShell window and start the self-report procedure:

```powershell
py -3 -m varyn.official_relay_pilot --manual-only --interactive
```

Walk through the seven fixed prompts. In the desktop, leave the model provider as `fake` and all VARYN API/network checkboxes disabled. Use a harmless synthetic task such as `SYNTHETIC: Give two ways to organize a short to-do list.` Choose ChatGPT as the *official app relay* target (this is separate from VARYN's API provider selector). Reject the browser-open dialog once, then approve it and confirm that the browser opens an official homepage. Reject a fresh clipboard packet preview once (existing OS clipboard must stay unchanged), then approve a new preview and manually paste the copied packet into the browser chat. Obtain a short harmless reply, copy it manually into VARYN's Message field, review it, and accept into temporary RAM. Switch the relay target to Claude or Gemini and inspect the new packet, which must quote the pasted reply as unverified reference text. If both official apps are available, complete the second manual paste. Click **Discard manual relay RAM state** and replace any clipboard contents that might contain the test packet.

If a target app is unavailable, cannot sign in, requires consent, or the owner cannot confirm an observation, mark `no` or `skip`. The report tool deliberately cannot infer actual login or connection success.

## Exact distinction: verified vs not verified

| Area | What can be asserted |
| --- | --- |
| Unit tests / hosted Windows Tk | Code paths, allowlisted URLs, consent gating, expiry handling, simulated button invocation |
| Owner manual pilot result | Only *owner self-reported* observations, if and when executed |
| Clipboard | Approved bytes copied to OS clipboard, but not proven pasted into the app |
| Browser open action | User-approved navigation request to pinned public official homepage, not an app account integration |
| Returned answer | User-pasted, untrusted and unverified provenance; never imported as official app history |
| Option C automatic consumer sync | **BLOCKED**, no proven bilateral official consumer-app history read/write authority |

The existing `varyn.option_c_gate` must remain blocked. Neither model APIs nor manual import/export count as automatic consumer-app synchronization. No personal conversations, user files, provider credentials, browser sessions or paid model calls are accessed by the pilot tool. The operating system browser may communicate with the official service after explicit user action.

## Evidence and next gate

Tests: `tests/test_official_manual_relay.py`, `tests/test_official_manual_relay_desktop.py`, `tests/test_official_relay_open_tk.py`, `tests/test_official_relay_pilot.py`. The exact completed Windows+Ubuntu workflow run ID, commit SHA and any failures must be recorded on PR #1 before calling the CI stage verified. Keep PR #1 **DRAFT** and `main` unchanged.

The meaningful next gate is actual owner-PC manual two-app acceptance, then evaluating whether the providers expose authorized, documented consumer-history read AND write semantics. Do not silently switch to unofficial browser scraping, cookies or API-only substitutes.
