# VARYN 17S-26 | One-click Windows owner pilot with actual desktop launch

Date: 2026-11-05. **Experimental; no physical owner-PC pilot performed here.** The code changes are on PR #1, OPEN/DRAFT, against unchanged `main`. Exact-head CI must be checked separately before calling the implementation verified.

## Product problem solved

Through 17S-25, VARYN had implemented actual Tk UI buttons for manual official ChatGPT, Claude and Gemini task transfer, local unverified return receipts, and bounded per-project synthetic working context. Yet proving that the owner can use this workflow required manually checking out a Git branch, launching two PowerShell terminals, and locating a separate CLI questionnaire. CI green measured programmatic widget invocation only, not real owner usability.

17S-26 packages one **owner-facing Windows entrypoint** that launches the VARYN desktop **in a separate local Python process** and walks the user through the existing seven official-app pilot questions plus three project-context checks. This removes a real delivery and acceptance bottleneck. It does not build a credential-based app integration or assert consumer-app sync.

## New owner experience

- `Try-VARYN-Official-Apps.cmd` is shipped at the **root of the existing source-only ZIP**. Double-click it as a **non-administrator** Windows user. It runs `py -3 -m varyn.owner_pilot_launcher --manual-only --interactive`, or the installed `python` equivalent if Windows Python Launcher is unavailable.
- `varyn/owner_pilot_launcher.py` explicitly refuses non-Windows or admin/unknown-elevation execution, spawns `[sys.executable, "-m", "varyn.desktop"]` with **no shell** and the repository root as working directory, and checks for immediate process exit. It strips common provider and developer token environment variable names from the **new child** (e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, GH_TOKEN); this is a bounded precaution, **not a complete OS secret isolation mechanism**. The desktop itself still runs with ordinary user permissions. Browser and UI remain entirely under the owner's control.
- After starting the child, the launcher guides the existing **seven fixed yes/no/skip** manual relay observations. It then adds **three** acceptance questions: exact project note review, explicit conflict/replace, and default-no-share vs explicit opt-in and discard. It never asks for provider account identifiers, actual transcript content, passwords, paths, cookies or keys.
- The combined output is printed as **one JSON object with fixed observation names and statuses only**. An all-yes result is labeled `owner_self_reported_pilot_pass` and retains flags `actual_owner_clicks_verified=false`, `automatic_bidirectional_consumer_sync_verified=false`, `consumer_history_read_authority_verified=false`, `consumer_history_write_authority_verified=false`, `safe_private_data_access_authorized=false`. A skipped/failed answer or failed desktop launch cannot become a success. No report file is created or uploaded by this program.
- The desktop may remain open when the questionnaire exits; close it normally. No clipboard reading or browser automation is done by the **launcher**; the desktop's separately approved official-site launch and clipboard commands remain governed by their own review gates. The child is not a production sandbox and this does not certify a physically observed click.

## How the owner actually runs it

1. Go to the [draft PR #1](https://github.com/naraya07pedro-spec/VARYN/pull/1), follow the **exact successful HEAD CI** link and download the artifact named `varyn-windows-source-launcher`. GitHub Actions artifacts may require signing into GitHub and the workflow currently retains the ZIP for seven days.
2. Extract the ZIP. Open the extracted `VARYN` folder. Python 3.12+ with Tkinter must already be installed on Windows. No third-party installer, signing certificate, compiled EXE, or bundled Python runtime is supplied.
3. Double-click **`Try-VARYN-Official-Apps.cmd`**. Stay on a **normal non-admin** Windows session. The script will open the Tk desktop and display its checklist prompts in the original terminal window.
4. Use exclusively harmless synthetic tasks and project notes beginning `SYNTHETIC:`. Keep the VARYN model provider on `fake`, with network/API consents off. Browser opening requires separate approval. If the browser logs into official services, that occurs in the normal browser, not through VARYN credential capture. Use two official apps where possible.
5. Record `yes`, `no`, or `skip` for each observation. Never paste transcripts or credentials into the terminal. Any `skip` means incomplete, not passed. Review JSON results locally; share only sanitized pass/fail flags if you want help diagnosing.
6. Close VARYN normally and clear or replace any clipboard test packet. The app's transient working board is not durable memory; it can reset on close.

If the artifact is unavailable, from an existing **clean** clone of the feature branch run `py -3 -m varyn.owner_pilot_launcher --manual-only --interactive` from its root. Never overwrite an uncommitted local checkout just to test.

## Verification and trust boundaries

- `tests/test_owner_pilot_launcher.py` uses dependency-injected subprocess and fixed reports to verify one exact child launch without shell, common credential environment stripping, strict Windows non-admin precondition, immediate failure handling, rejected malformed answers, nonzero status on skipped observations, and never asserting official app history read/write or physical human clicks.
- `tests/test_desktop_packaging.py` and `tests/test_acceptance_packaging.py` verify the source archive contains the one-click script and Python module, includes no `.env`, SQLite, binary, local browser data or secrets, and fails closed if required inputs are missing.
- `.github/workflows/memory-checks.yml` runs dedicated regression gates plus the existing full suites on Windows and Ubuntu, builds the deterministic source-only ZIP, verifies the entrypoints, and publishes the Windows artifact for seven days.
- GitHub-hosted tests can prove packaging and deterministic contracts, **not** that a human successfully double-clicked the archive on their own PC, reached both signed-in official apps, or manually pasted a reply. Only the owner's real-device pilot can supply that self-reported acceptance evidence.
- Default browser requests to the actual ChatGPT/Claude/Gemini sites happen **only after the user's separate explicit action** in VARYN; launcher itself makes zero HTTP requests. The shell and installed Python interpreter are trusted local prerequisites. The script does not bypass Windows UAC or request admin rights.
- `varyn.option_c_gate` remains **blocked**. Official browser homepages and manual clipboard transfers cannot be advertised as automatic official consumer-app history/memory synchronization. Further work needs provider-sanctioned authenticated history **read and write** capability evidence, not speculative cookie scraping or API-only substitution.

## Next decision gate

The owner should actually run this artifact on their Windows machine and submit only the fixed status results or any specific redacted error. Then prioritize observed UX blockers and provider-sanctioned integration feasibility, rather than increasing simulated test counts indefinitely. **Production private-file permissions and automatic provider sync remain disabled.**
