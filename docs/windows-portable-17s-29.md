# VARYN 17S-29 | Experimental no-Python Windows portable app

Date: 2026-11-05. **Build and exact-head verification are pending at this document write.** PR #1 stays OPEN/DRAFT against unchanged `main`, and no user-private OS file access, provider history synchronization, or paid model-provider API is enabled here.

## Problem and choice

17S-28 supplied a real manual official-app workbench, but the GitHub Actions deliverable was a **source-only ZIP** requiring the owner to install Python 3.12+ and Tkinter. This is a major practical barrier, especially for a laptop with limited RAM and an owner who primarily wants to test the product, not administer Python. A new optional portable Windows artifact is a higher-leverage next step than another simulated AI delegation layer.

Packaging choice: **PyInstaller 6.22.3 pinned, x64 Windows runner, `--onedir --windowed`, Python 3.12**. The entire `VARYN-Portable` folder is extracted and launched in place. We deliberately do not use `--onefile` which adds extraction on each run and may be slower/inconvenient for repeated use. Build on Windows, not a Linux cross-compile. Official docs: https://pyinstaller.org/en/v6.22.3/ and https://pyinstaller.org/en/v6.22.3/usage.html . The PyInstaller version is pinned, but indirect dependencies and Windows hosted image are **not** completely reproducibly pinned, and the binary **is not code-signed**.

## Implemented files

- `varyn/portable_entry.py`: distinct Windows portable entrypoint. Refuses normal launch on non-Windows or elevated / unknown-elevation tokens; the hosted `--smoke-only` path creates a **real** Tk root and official-app workbench, verifies the controller's `offline_simulation` mode, and closes without network, browser or clipboard actions. Normal portable launch uses `DesktopController(allow_live_providers=False)`, opens the existing parent desktop and automatically foregrounds the 17S-28 manual workbench. The same existing exact review, clipboard, external browser consent, RAM-only notes and local callback audit remain. It never adds model APIs or a hidden official account connector.
- `varyn/portable_release.py`: generates a bounded file-by-file SHA-256 inventory as `BUNDLE-SHA256.json`, checks the EXE has the Windows `MZ` header, requires `_internal` and safety README, excludes arbitrary archives and known private-data suffixes, refuses symlinks, excessive files/size and unexpected modifications. The standard PyInstaller internal `base_library.zip` is permitted as an explicit exception. This is **release package integrity checking only**, not an independent signed authenticity claim.
- `README-PORTABLE.txt`: owner-readable start steps and warnings packaged next to `VARYN-Portable.exe`. Does not request elevation, registration, provider credentials, installation or antivirus bypass.
- `tests/test_portable_windows_release.py`: portable launch offline-model gating, no implicit provider callbacks, desktop smoke contract, admin refusal, manifest tamper detection, fake signed/sync claims rejected, missing files and extra data/secret files refused. The final Windows CI job must verify an actual PyInstaller-built folder and a subprocess invocation of the compiled EXE with `--smoke-only`.
- Original `varyn/package_desktop.py` **source-only ZIP is not removed or weakened**. It remains a fallback and a way to inspect/audit all Python source without trusting a newly compiled executable.

## What the portable EXE does and does not do

Does:
1. Open a Tk desktop and focused official ChatGPT/Claude/Gemini *manual* workbench without separately installed Python.
2. Require owner acceptance of each pinned public homepage open, exact outgoing clipboard packet, unverified pasted reply and temporary project-note sharing.
3. Keep local workbench and context RAM-only and synthetic-only for this experimental build. Default model provider `fake`; live model APIs unavailable through its desktop controller.
4. Let the owner inspect or discard local callback audit, and print explicit unverified/unsynced status.

Does **not**:
1. Access official consumer-app accounts or chat history automatically, synchronize memories in both directions, scrape browser cookies, verify external paste delivery or authenticate provider response provenance.
2. Provide a secure production Windows AppContainer sandbox or independently verified execution on the owner's PC; a runner's GUI smoke test is not user acceptance.
3. Offer a code-signed trusted publisher chain, Windows installer or auto-updater. Source is GitHub; package is a separate unsigned artifact.
4. Guarantee that no other user-initiated desktop public tool can use network. Some existing public GitHub features still support separate owner-authorized network operations, which should be left OFF during the pilot.
5. Store confidential data safely or sanitize user-entered secrets automatically. Use only `SYNTHETIC:` tests.

## How to run and verify on Windows

From PR #1, open the **exact successful commit** GitHub Actions run, navigate to Artifacts, and download `varyn-windows-portable` (if this artifact appears after full Windows build success). Extract the entire ZIP to a folder in your user profile, then run **`VARYN-Portable.exe`** as your regular Windows user. Do not run elevated. Keep `_internal` next to it. The portable EXE is unsigned: if Windows Defender or SmartScreen blocks it, do not bypass/disable security controls. Use the source ZIP with an existing Python runtime instead.

A local checksum check in normal PowerShell, from the extracted folder:

```powershell
$manifest = Get-Content .\BUNDLE-SHA256.json -Raw | ConvertFrom-Json
$actual = (Get-FileHash .\VARYN-Portable.exe -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $manifest.main_executable_sha256) {
    throw "VARYN executable hash mismatch; do not run"
}
```

**A malicious actor can edit both an unsigned EXE and its adjacent JSON.** Compare the SHA/hash with the actual trusted GitHub Actions run and the exact SHA. Do not represent this hash manifest as a signature or a malware safety guarantee.

Run a harmless synthetic two-app relay and note the concrete UI/launch errors. The source-only `Try-VARYN-Official-Apps.cmd` and pilot reporter remain supported. No owner-PC test has been observed in this chat.

## Verification gate and next priority

- Both full Windows+Ubuntu regression suites must succeed on **the exact final code/doc HEAD**.
- Separately, the optional Windows portable build must succeed under pinned PyInstaller, create and verify a manifest, run `VARYN-Portable.exe --smoke-only` on a hosted Windows GUI session with exit code 0, and actually publish the full one-directory bundle as an artifact. An artifact is not a signed certified application.
- Do not call 17S-29 a fully verified portable release unless both gates and artifact presence have been checked. The physical owner's usability, false-positive AV behavior, actual signed-in ChatGPT/Claude/Gemini relay and device-specific RAM footprint remain **unknown**.
- The biggest unresolved product requirement remains **Option C**: official consumer chat history/memory automatic bilateral read-and-write authorization remains unavailable/unverified and is not silently replaced by model API calls, manual clipboard transfer or a packaged GUI.
