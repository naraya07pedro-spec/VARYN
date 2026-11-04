# VARYN 17S-10 | Real Windows kernel restricted-token read-denial proof

Date: 2026-11-05. This is an **offline, Windows-hosted OS capability proof**, not a deployed sandbox. It preserves the user's Option C requirement and does not grant private access to any provider, model or tool.

## Why this checkpoint exists

The production public GitHub subprocess runs under the desktop owner's user SID, with a constrained Job Object and Low Mandatory Integrity Control (MIC). The Windows MIC default does **not** prohibit the process from reading same-user personal files. Therefore claiming that it isolates private reads would be a dangerous false assertion. Broader/private/mutating tool use stays disabled.

Microsoft specifies that a token created using \`CreateRestrictedToken\` with **restricting SIDs** faces **two OS DACL access checks** and both must grant access. A normal owner-readable file need not grant the restricting SID. A **restricted process** could eventually use a restricted primary token at creation; this checkpoint does not implement that process spawn or its app-container-level networking.

Primary Windows documentation:
- https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken
- https://learn.microsoft.com/en-us/windows/win32/secauthz/restricted-tokens
- https://learn.microsoft.com/en-us/windows/win32/secauthz/mandatory-integrity-control

## Exact code and evidence

- \`tests/windows_restricted_read_probe.py\`: native Win32 \`OpenProcessToken\`, \`ConvertStringSidToSidW\` (restricting SID \`S-1-5-12\`), \`CreateRestrictedToken(DISABLE_MAX_PRIVILEGE)\`, \`IsTokenRestricted\`, \`ImpersonateLoggedOnUser\`, and guaranteed \`RevertToSelf\`/handle cleanup. Performs *one fresh file open* with the OS-issued restricted thread token in a disposable child Python process, after verifying the same synthetic file is readable without restrictions. Output is bounded, JSON, and has explicit \`production_subprocess_restricted: false\`.
- \`tests/test_windows_restricted_read_probe.py\`: creates a disposable file with literal bytes \`varyn-synthetic-owner-only\`, launches a separate \`-I -S\` Python subprocess with no provider environment secrets or network intent, and requires **positive control read OK and restricted read permission denied by Windows**. The parent independently reads the unchanged bytes after the child exits. Missing or absent input never counts as a denial proof.
- Hosted CI runs the same test module on Windows and Ubuntu. The Windows-specific proof must **actually execute and pass**; on Ubuntu it is intentionally skipped and a portable negative test confirms no Windows attestation. The probe lives under \`tests/\` and is deliberately excluded from the desktop source-only ZIP.
- Existing \`ProcessRepoFetcher.status()['os_sandbox']\` and \`['windows_mic_blocks_private_reads']\` remain **False** and the production Windows GitHub child still has its previous privileges. It does not invoke this probe. Tests prevent a silent claim that a sandbox was integrated into production.

## The critical unfulfilled work

This test proves **thread impersonation with a restricted access token** on one synthetic file. It does not prove a restricted **primary token from process start**, that Python and dependencies will load and network correctly under restricted rights, that the child cannot read *all* user data, that existing handles are revoked, or that the real owner PC has the same policy. It does not prevent same-user malware or include AppContainer / WDAC / private filesystem or arbitrary tool access.

**Next gate:** choose and implement a reproducible restricted-primary-token process launch **before** any untrusted code runs, with explicit access to approved executable/library resources, no broad read authority, no inherited sensitive handles, and fail-closed native attestation before user inputs or external calls. Demonstrate this with actual owner-only synthetic files and hosted Windows network/packaging tests. Do not allow any sensitive tool until that holds. Validate owner-device acceptance independently.

PR #1 stays draft; \`main\` untouched. Final CI on exact head is required before this checkpoint may be called verified.
