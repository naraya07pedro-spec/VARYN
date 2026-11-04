# Checkpoint 17H: Local Windows synthetic acceptance and hardware gate

**Date:** 2026-11-04 (Asia/Jakarta).
**Purpose:** Give the owner a bounded, inspectable, offline acceptance procedure before any private-file access is even considered.
**Rules:** No admin privileges required, no credentials, no paid models, no user folder picker, no arbitrary filesystem input. No network/provider requests from this acceptance probe.

## Safe executable self-check

From an inspected VARYN repo checkout on its draft branch, open normal Windows PowerShell in the repo directory (NOT as Administrator). Run:

    py -3 -m varyn.desktop_acceptance --synthetic-only --json

What this verifies, using only VARYN-created temporary sample.txt and notes.md:
- The existing native Windows scoped reader can open the temporary sample folder under a fixed local drive.
- Read-only, non-recursive, quota-limited folder listing returns exactly two known synthetic names; the report itself includes NO filenames, paths, or file contents.
- A real Python in-process timer expires a one-second grant, closes its OS handle, and requests fixture deletion **without touching the UI or polling status**.
- The previous grant cannot be used after expiry. Cleanup in finally runs even on a failed check.

Expected: JSON with passed:true and four true checks. An error returns nonzero exit and never embeds raw private paths in its report. This self-test may still FAIL on a particular PC because of Python/Tkinter installation, a non-fixed TEMP drive, filesystem restrictions, antivirus or environmental problems; a failure is evidence to investigate, not a reason to bypass protections.

## Separate real desktop smoke and user interaction

1. Confirm Python 3.10+ installed with Tkinter. From the same ordinary PowerShell prompt, run:

       py -3 -m varyn.doctor --gui-smoke --json

   A GUI-smoke PASS only verifies that the actual Tkinter window can be created and updated in the local graphical session. It does **not** click the consent dialogs or exercise real user interaction.
2. Launch desktop:

       py -3 -m varyn.desktop

3. Keep provider on fake; do not enable network, add API keys or type private data.
4. Click **Create & grant VARYN demo folder** and choose **No** once. This must leave no active grant.
5. Repeat and choose **Yes**, then press **Inspect test-folder count**. It must show a count of two, without filenames, paths, or file contents.
6. Use **Revoke test-folder grant**; repeat Inspect and confirm access is denied. Grant again and close/reopen the desktop. No old grant should persist.
7. For the idle-expiry check, approve a new demo and leave the app idle past the default five-minute lease; inspection must refuse the expired grant. Under normal operation its sample folder should have been cleaned by the timer without a click, but do not claim a visual guarantee or gather filesystem paths for this check.

**These real GUI-click and physical-owner-machine steps remain UNVERIFIED until actually completed by the user.** A hosted GitHub Windows runner cannot substitute for physical PC sleep/resume, user dialogs, antivirus, hardware RAM pressure or window behavior.

## CI checks and output restrictions

The new command is exercised in the Windows and Ubuntu CI matrix as a command and by focused tests/test_desktop_acceptance.py regression cases. The command is not an executable installer and does not launch a GUI; its machine-readable report explicitly states owner_windows_gui_verified:false and ui_clicks_performed:false.

The existing source-only ZIP CI artifact bundles VARYN Python modules including this acceptance probe, but **does not ship Python** or a compiled executable. GitHub artifact availability is temporary. Verify source and extract only trusted packages. Avoid elevated shells and never run downloaded scripts blindly.

No local PC or account data has been used by the GitHub-hosted checks.

## Open blockers / stopping conditions

- Any missing/unsafe native Windows API, changed handle identity or cloud placeholder must fail closed rather than fall back to scanning personal paths.
- A temporary permission remains a trusted Python caller assertion; it is NOT a Windows ACL sandbox or cryptographically authenticated OS consent.
- Python timer or deletion failure means cleanup may be late or incomplete; sudden process death can leave harmless example files. The probe does not guarantee crash-safe zero residue.
- No real file browser or personal folder access is exposed by the current desktop demo.
- No official ChatGPT/Claude/Gemini consumer-app account/history synchronization was attempted. See docs/official-app-sync-feasibility-17h.md.

**Next gate:** Human-verified Windows GUI steps and formal OS process/consent isolation. The current implementation is a tested synthetic prototype, not general-purpose private file access.
