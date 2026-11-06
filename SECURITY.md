# Security Policy

## Experimental software, not a trusted production environment

VARYN's Windows Portable binary is **unsigned**; it is built in a hosted GitHub Actions runner. It is not a signed publisher release, a robust sandbox, an audited vault, or a confidential-data processing system.

**Do not use it with customer secrets, sensitive personal chats, production accounts, production infrastructure, or valuable filesystem write permissions.** Do not disable Windows Defender, SmartScreen, or other operating system protections to install it.

## Reporting vulnerabilities

Please **do not post exploitable details, credentials, private file contents, or user data in public issues**. Check the repository's **Security** tab for a private vulnerability-reporting option, if enabled. If no private channel is configured, request a secure reporting contact through a non-sensitive issue without publishing vulnerability details.

Useful reports include affected commit, environment, minimal redacted reproduction, impact, and proposed mitigation. Do not probe third-party provider accounts without authorization.

## Trust boundaries

- All provider chat calls require independent network opt-in, reviewed model metadata, per-request approval, and local OS process credentials.
- A provider API request is **not** consumer ChatGPT/Claude/Gemini account synchronization.
- Local cost estimation **does not cap provider billing**. A 9Router localhost hop may use different upstream routes.
- The local data prototype is not guaranteed encrypted at rest, comprehensively secret-scanned, or secure against malicious processes running as the same Windows user.
- User-review dialogs do not replace OS authorization boundaries.
- GitHub Actions status and checksums are useful integrity signals but do **not** replace code signing and provenance independent of the build host.

## Supported releases

There are **no production supported versions**. Report problems against an exact commit SHA and identify whether they occur in source Python, Windows Portable, or a mocked/offline run.
