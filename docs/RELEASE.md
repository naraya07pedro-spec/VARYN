# Experimental Windows distribution | Release checklist

**As of 2026-11-06:** [v0.1.0-alpha.1](https://github.com/naraya07pedro-spec/VARYN/releases/tag/v0.1.0-alpha.1) was published successfully as a **public experimental GitHub Pre-release** from exact source commit `ac547f15c6db10fd25754cb4e0e2bbdce8d12906`. No signed installer, publisher certificate, user-device acceptance, or stable support claim.

## Historical verified precursor build (17S-46 before public prerelease)

- Source commit: `b52a774241825f596fc0ccb063de190a9b520994`.
- GitHub Actions run: https://github.com/naraya07pedro-spec/VARYN/actions/runs/42162535996
- Status: Ubuntu test job SUCCESS; Windows test job SUCCESS; Windows Portable bundle job SUCCESS.
- Artifact: `varyn-windows-portable`, ID `13477144523`.
- GitHub artifact ZIP SHA-256: `13dd7e068698840e001c6556f4e7cfa746ca4509e1b514c310d329bc476a733b`.
- CI artifact expires: `2026-11-13T04:31:32Z`. GitHub Actions artifacts are not durable public releases.
- The embedded files also have a `BUNDLE-SHA256.json` integrity manifest. That manifest alone is **not** a signature.

## Actual published prerelease

- Tag: `v0.1.0-alpha.1`.
- Exact tagged source commit: `ac547f15c6db10fd25754cb4e0e2bbdce8d12906`.
- Actions run: https://github.com/naraya07pedro-spec/VARYN/actions/runs/42170609120 ; Ubuntu, Windows and portable build as well as release publication jobs **all SUCCESS**.
- Public binary: https://github.com/naraya07pedro-spec/VARYN/releases/download/v0.1.0-alpha.1/VARYN-Windows-x64-v0.1.0-alpha.1-unsigned.zip
- Published ZIP SHA-256: `dbd81452b9af7322da201979bcc2a92112b8bd8c67994ad76938c0498bc3b162`.
- Byte size: `13798293`.
- The release tag predates this documentation correction. Historical CI artifact digests above are for **different ZIP bytes**; never mix them with the public release ZIP digest.

## Release reproduction checklist for future tags

1. Publish a tag pointing to the exact reviewed source commit **without merging draft PR #1** unless separately approved.
2. Download the matching Actions artifact, verify the exact ZIP digest above, verify the internal file manifest, and inspect the archive contents for unexpected data.
3. Attach the **actual verified ZIP** as a Release binary; do **not** link a file from source that merely looks like an EXE. Publish release notes including the unsigned, experimental status and a no-secrets warning.
4. Link the released asset from README and verify it can be downloaded anonymously. Update the real Release URL and digest only after publication.
5. Record a genuine, sanitized screenshot/GIF from a real GUI launch; owner-PC acceptance must be stated separately.

**The initial GitHub Pre-release has been independently verified by reading the Releases API.** The release publishing workflow runs only on intentional `release:` commits and does not merge the draft PR into `main`.

## Release notes draft

**VARYN experimental Windows pilot (17S-46)**

- Unsigned Windows x64 portable desktop, normal user only, no Python installation required.
- Owner-verified model offers, cost estimate, optional provider model discovery and one request at a time to pinned OpenRouter, DeepSeek or explicitly authorized local 9Router.
- Owner-typed non-synthetic prompts require an additional consent gate and the exact request is reviewed before network dispatch.
- Manual synthetic handoffs among official AI apps, and experimental local memory components.

**Not supported:** production secrets, autonomous universal agent, guaranteed billing cap, native two-way official consumer history sync, signed Windows installer. Experimental use only, no production warranty.
