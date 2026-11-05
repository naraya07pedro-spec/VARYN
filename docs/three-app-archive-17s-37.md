# VARYN 17S-37 | Completed three-AI archive, Windows DPAPI, read-only reopen

Date: 2026-11-05. Previous checkpoint 17S-36 retained three full user-pasted synthetic replies only in RAM. Closing VARYN destroyed them. Earlier DPAPI Save/Restore supported synthetic editor drafts, not reviewed multi-app replies.

## New workflow
After all three guided manual ChatGPT → Claude → Gemini stages have been locally reviewed, the user may click **Save completed 3-AI encrypted archive**, inspect the exact three full synthetic replies and local provenance in the original scrollable approval modal, then select a **new** `.varyn-archive` filename. The file is Windows-user-profile-bound DPAPI ciphertext written with the existing no-overwrite `varyn.dpapi_vault.write_sealed`. No plaintext temporary file is used.

In a future app session the owner may explicitly choose **Open saved 3-AI archive read-only**, select the file, inspect the exact decrypted records before separate approval, and open a scrollable read-only window. Importing archived text into live relay state is **not supported**: no previous approval, return receipt, provider login, clipboard, model interaction, relay hop counter, or next-stage execution state is restored.

The exact `varyn.completed_synthetic_three_app_archive.v1` schema includes three ordered, fixed-provider `SYNTHETIC:` replies, locally bound digest fields and mandatory `read_only=true`, `manual_only=true`, all authority flags false. Local digests detect inconsistent pasted text, **not** remote authenticated provider identity. Changed, truncated, extra/unknown schema fields, altered local content and illegal claims fail closed. Saving only allows completed 3/3 stages. File extension and payload sizes are bounded.

## Verification gates
- `tests/test_three_app_archive.py`: exact schema, authority flag denial, incomplete flow, wrong order, changed locally bound reply, strict extension, DPAPI-only storage and non-Windows refusal, native Windows encrypted roundtrip/overwrite/corruption refusal.
- `tests/test_three_app_archive_tk.py`: native hosted Windows Tk three reviewed guided stages; denied vs approved archive save, actual Windows DPAPI; workbench close/reopen, denied vs approved read-only archive load, zero restored live relay state/provider requests.
- `.github/workflows/memory-checks.yml`: dedicated cross-platform and Windows-native Tk checks before the existing full regression, frozen Windows portable smoke and 4-process draft restart gates.
- `README-PORTABLE.txt`: owner instructions and explicit warnings.

No signed-in official ChatGPT, Claude or Gemini account histories/memories are accessed, and no automatic bidirectional synchronization exists. Opsi C remains the target; this read-only archive is a narrow user-mediated continuity step, not a replacement. Windows DPAPI is tied to a specific OS profile and this is not a multi-device backup or secure storage against compromised local users. Use only fictional synthetic data. The actual owner's PC/SmartScreen behavior is unverified.

PR #1 must remain OPEN/DRAFT, `main` unchanged. Exact-commit CI proof must be captured before calling the stage green.
