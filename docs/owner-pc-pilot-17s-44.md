# 17S-44 | Owner-PC Pilot Launcher and Complete Portable Integrity Verification

Date: **2026-11-06 WIB**. The original Option **C** native automatic two-way consumer-app ChatGPT, Claude and Gemini history/memory synchronization remains **BLOCKED**. Owner-selected Option **B** permits distinct official multi-provider APIs, and the 17S-43 GUI now offers an explicit model-ID catalogue request. This step prepares the **actual owner-owned Windows PC** for an acceptance trial without ever asking for an API key in chat.

## Delivered owner functionality

`Start-VARYN-OwnerPilot.ps1` is an **OPTIONAL, UNSIGNED** Windows PowerShell 5.1-compatible launcher shipped in the *same portable folder* as `VARYN-Portable.exe` and `_internal`. It starts in offline mode, and never authorizes an actual provider network request itself. It performs **full bundled file SHA-256 verification** against the included `BUNDLE-SHA256.json` before attempting to launch a process, requiring exactly matching files and a complete `_internal` folder, including the launcher script itself. It refuses a missing, changed, unexpected or symlink/reparse-point file. `-VerifyOnly` checks integrity without launching VARYN or requesting credentials; this read-only mode may run from an elevated CI runner, but **actual application launch MUST be under a non-elevated Windows user**.

The next gate is still **independent distribution trust**. The manifest and launcher are unsigned and could both be replaced by an attacker. The owner must compare the **whole downloaded ZIP SHA-256** against the exact GitHub Actions artifact digest published in PR #1 and confirm the expected source commit, separately from the adjacent manifest. A local manifest comparison alone cannot verify the publisher. Never disable Microsoft Defender, SmartScreen, UAC, or PowerShell execution policy to make it run.

### Exact normal-user commands, from the EXTRACTED portable directory

```powershell
# 1. No network, no credentials, no app launch:
powershell.exe -NoProfile -File .\Start-VARYN-OwnerPilot.ps1 -VerifyOnly

# 2. Launch offline with no inherited OpenRouter/DeepSeek/9Router key:
powershell.exe -NoProfile -File .\Start-VARYN-OwnerPilot.ps1 -Provider offline

# 3. OPTIONAL, only after personally obtaining an official API key:
powershell.exe -NoProfile -File .\Start-VARYN-OwnerPilot.ps1 -Provider openrouter
# Or -Provider deepseek, or -Provider 9router
```

The provider-specific command displays a **hidden Windows PowerShell SecureString prompt**. The key is transiently converted into the selected provider's **child process environment variable** only to launch the GUI, then removed from the script's own process environment in `finally`. The native `SecureString` buffer is released with `ZeroFreeBSTR` where applicable. No key is put into shell arguments, clipboard, repository, PowerShell history, file, log, or ChatGPT by this launcher. The VARYN child still possesses its key in process memory/environment until it exits; other processes with sufficient privileges may inspect it. This is **not** a production credential vault. A crash cannot guarantee all managed-string memory is zeroed.

The launcher does **not** call an external API, `setx`, change registry keys, request elevation, modify Windows execution policy, or silently create a task. If script execution is blocked by corporate/Windows policy, **do not bypass it**. You can still open the EXE normally for offline FAKE and manual-app tests if Windows allows it.

### Owner-PC acceptance sequence and evidence

1. Download the **exact-HEAD `varyn-windows-portable`** ZIP from GitHub Actions, first verify the ZIP SHA-256 against the independently published digest, extract the **whole folder**, and check Defender/SmartScreen without bypassing it.
2. Run `-VerifyOnly`. Note whether full inventory PASS or BLOCKED; a pass is a **local integrity self-check**, not a signed publisher identity.
3. Run `-Provider offline`; verify the Model Control Center opens as a **non-admin** Windows user. Register fictional `fake/fake-test` with price 0 for both directions and freshly reviewed/test-only flags. Preview, refuse a fixed synthetic request, and then separately approve a fixed fake request. Confirm `FAKE:` reply and no real provider receipt or network.
4. OPTIONAL real external provider: obtain an official key and choose `-Provider openrouter` or `-Provider deepseek` in a **new launch**. **9Router** additionally needs an authorized local installation, config and upstream account permission. The launcher alone never proves a model can be used or costs nothing.
5. In the Model Control Center choose **Discover model IDs**; set GET network toggle ON and separately approve exact `GET /models`. An ID appearing does **not** verify account inference permission, costs or availability. Separately check current input/output per-million-token prices and provider-specific limits in the official UI.
6. For a single fictional `SYNTHETIC:` prompt, manually register the reviewed model and both rates, set a conservative estimated output limit and price ceiling, check live network ON and approve one exact model request. The estimate is **not a provider hard spending cap**, and 9Router/OpenRouter may choose different upstream models or charge even if the call appears to fail. Stop on unknown pricing or missing entitlement. No automatic retries or background requests.
7. If a non-FAKE response is parsed, the **17S-41 metadata-only receipt** may be reviewed and saved to a NEW JSON path. The receipt is not cryptographic authentication of the responding model or proof of charges. Do not paste API keys, full conversations or cookies into a GitHub PR or this chat.

## Verification scope

- Source: `Start-VARYN-OwnerPilot.ps1` provides a verification-only path, strict non-admin launch, default OFFLINE, hidden per-provider key prompt, and cleanup without persistent credentials.
- Packager: `varyn/portable_release.py` requires the launcher **inside** the bundle and hashes it in `BUNDLE-SHA256.json`. No .env, session cookies or private log included. `.github/workflows/memory-checks.yml` copies launcher before manifest creation, tests PowerShell syntax, runs the **actual bundled PowerShell -VerifyOnly**, and still performs unsigned frozen EXE Model Center smoke plus four frozen DPAPI synthetic-process checks.
- Tests: `tests/test_portable_owner_ps1.py` checks static safety and executes real **Windows PowerShell** against a synthetic portable folder; verifies full hash PASS and refusal of a tampered launcher, unexpected extra file or missing file. `tests/test_portable_windows_release.py` checks hash-integrity of the launcher alongside EXE/runtime and refuses tampering.
- Do not confuse this test with **real owner-PC acceptance**, signed binary publisher verification or actual remote OpenRouter/DeepSeek/9Router authentication. Automated CI cannot use the user's local key or demonstrate an account-specific billing event.

**Release rule:** exact final SHA Ubuntu+Windows regression and frozen unsigned Windows Portable 3/3 CI success required; PR #1 remains OPEN/DRAFT and `main` unchanged.
