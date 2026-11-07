# Stage 10: First real-provider acceptance on owner's Windows device

This stage gives the owner a small, safe end-to-end test that is more
realistic than claiming that every simulated CI test proves production.

## What to do in the Windows preview

1. Download VARYN's unsigned Preview artifact built by the CI workflow on
   the Stage 10 branch, review the SHA-256 manifest and extract it to a
   trusted folder. Do NOT disable system security controls to run it.
2. Open VARYN Chat. Configure a real **reviewed** OpenRouter or DeepSeek
   model and its fresh pricing quote. Provide an API key within the local
   app configuration, not in GitHub or in chat with a third party. Enable
   the existing one-session network permission.
3. Open **Public GitHub agent**. In that window check
   **Enable ONE reviewed provider acceptance session (may bill)** and
   choose **Test 1 GET + 1 AI**.
4. Review the top-level summary. The test targets ONLY the public
   \`python/cpython\` repository, reads five public metadata fields,
   and prepares one outgoing model prompt containing those fields.
   The estimate is bounded by a *quoted* ceiling of 50,000 micro-USD
   (US$0.05) per request, NOT by a provider spending cap.
5. Approve the GitHub GET separately. Inspect the actual text of the
   model request and approve that separately. Declining either action
   prevents the corresponding network dispatch.
6. When the run completes, open **Last provider smoke receipt (offline)**.
   Confirm the transport is \`configured_network_adapters\`, GET and
   model attempt counts are each 1, the model identifier reported by
   the provider matches the reviewed choice, and the resulting structured
   JSON matches the public GitHub tool observation.
7. If either action was rejected, canceled, or uncertain, inspect the
   persisted non-success status. An attempt is reserved BEFORE its
   network actions, with one smoke attempt per UTC day across restarts.
   No retries happen automatically. Running again on the same UTC day
   will be denied.
8. Consult the provider's authenticated dashboard yourself for the
   model request and actual provider charges, which VARYN does not
   fetch or attest. If those records do not match, DO NOT treat the
   acceptance as production verified.

## What the receipt actually contains

The local SQLite store at \`%LOCALAPPDATA%\VARYN\learning.sqlite3\`
retains only:
- random session ID, UTC day, start and finish times and status
- selected provider and SHA-256 hash of model name
- source_kind: \`configured_network_adapters\` or
  \`injected_test_or_custom_transport\`
- count of approved attempted reads/requests (at most 1 each)
- local comparison result against the received GitHub observation
- SHA-256 digest of the observed public fields and provider-reported
  response ID (only when provided)
- reported input/output token counts, if provided
- reviewed local estimate and an integrity checksum of the receipt

It does NOT retain provider API keys, raw prompts, the model's response
content, raw response IDs, private repository data, invoices or CSV files.
SQLite is plaintext and not an authenticated audit archive; a local
attacker with write access can change both rows and hashes.

## Evidence status and limits

**Network adapter configured** is NOT an independent attestation that the
owner's actual paid account was charged or that a particular model ran
internally. A provider-reported model name is an upstream claim, not
cryptographic attestation.

A passing smoke result means that one output agrees with one approved,
received public GitHub tool observation. It does NOT prove generalized
reasoning quality, successful automation, true long-term learning or
production readiness. This smoke does NOT promote procedural skills.

GitHub Actions tests use injected network and synthetic provider replies,
always marked as such. They do NOT consume live account funds and are
NOT equivalent to running the preview with the owner's real key.

## Failure policy

- No explicit owner approval: no network action.
- Invalid reviewed quote, fake model, unavailable API key, exceeded shared
  request/token budget: fail before any request.
- Missing/mismatched provider-declared model ID: no fact-verification pass.
- Wrong metadata schema/fields/types: verification_failed.
- Network failure, uncertain dispatch or crash: needs_review or
  running_or_interrupted. NEVER automatically replay.
- The session is limited to one approved public GET and one approved
  provider request. It cannot write to GitHub, read private files, or
  access private conversations.
- Spending estimate is NOT a hard provider billing ceiling. Actual cost
  cannot be known without independently authenticated billing evidence.

## Development checks

    python -m unittest discover -s tests -p "test_owner_provider_acceptance.py" -v
    python -m unittest discover -s tests -p "test_consumer_workspace_tk.py" -v

Additional prior regression suites run in GitHub Actions. The Windows
build remains an unsigned preview, not an installed task, always-on
background service, or automatic VPS deployment.
