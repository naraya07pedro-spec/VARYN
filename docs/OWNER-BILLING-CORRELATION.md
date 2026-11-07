# Stage 9: Offline, owner-supplied provider billing correlation

VARYN Stage 8 recorded a reviewed price **estimate** and provider-reported
token totals. This was never evidence of actual provider charges. Stage 9
adds an optional, local correlation of **ten actual provider-reported response
IDs** to **ten owner-supplied cost entries**.

## Scope and acceptance

- The approved OpenRouter/DeepSeek response's bounded \`id\` string is
  converted to SHA-256 in memory. The raw ID is **never persisted or shown**
  in VARYN's learning database. Missing IDs cannot be invented.
- For the five-public-repo/ten-model-call evaluation, all ten successful
  provider responses must report **distinct IDs**. The approved VARYN
  runtime stores only their fingerprints under the random session ID.
- Use the **Last evaluation receipt** UI first. A complete session must
  have a clean local receipt checksum, five public reads, ten successful
  model responses, zero uncertain calls and ten distinct ID hashes.
- Next, acquire your own provider's original billing/usage evidence.
  **VARYN does not access the provider account, fetch invoices, authenticate
  the user-supplied source, or infer provider charges from token counts.**
- Normalize the relevant ten rows yourself into a local UTF-8 CSV using
  the EXACT raw response ID, one ID per request, and the corresponding
  charged amount in integer millionths of US dollars (micro-USD):

      request_id,charged_micro_usd
      gen-example-a001,23
      gen-example-a002,31

  The example has two illustrative rows. The actual import requires exactly
  ten rows, matching the current recorded session IDs. micro-USD is an
  integer unit: 1 USD = 1,000,000 micro-USD. Do not round a provider's
  native decimal figures without recording/understanding the precision.
  **Providers do not necessarily offer a native export in this shape.**
  Manual normalization by the owner is required.
- In the Windows **Public GitHub agent** window, select
  **Reconcile owner billing CSV (offline)**, choose the CSV, review its
  total and variance from the local estimate, then explicitly confirm.
  The entire process is offline. No original CSV path/content is saved.
- The stored result says **owner-supplied** and
  **provider account NOT authenticated**. A locally matching set of request
  IDs does NOT prove an invoice's authenticity, billing attribution,
  provider cost correctness, or monetary spending limit.

## Reject-by-default behavior

- No completed acceptance receipt, malformed/corrupted local digest,
  fewer than ten unique provider response IDs, or any unsuccessful/uncertain
  model call -> import rejected.
- CSV wrong header, extra/missing/duplicate rows, wrong amount type,
  negative amount, overlong text, nonexistent or differently spelled IDs,
  unexpected extra columns, or huge file -> rejected.
- No external provider call is made during reconciliation. An incomplete
  or missing upstream \`id\` never becomes a fake matched row.
- The owner must approve the exact summary before storing. A session's
  billing comparison is immutable in VARYN; it cannot be silently edited.
- Only request ID hashes, total cost, difference, 10-row source fingerprint
  and a local checksum remain in SQLite. This is not encrypted or
  externally signed; a database-writing attacker can tamper with both data
  and checksums.
- Never paste private API credentials, access tokens, card details, account
  identifiers, or original invoice attachments into this CSV.

## Implementation

- \`varyn/gateway_chat.py\`: bounded parsing of untrusted provider response ID
- \`varyn/universal_gateway.py\`: only SHA-256 of reported ID exposed
- \`varyn/owner_live_evaluation.py\`: per-success response fingerprint capture
- \`varyn/owner_billing_reconciliation.py\`: strict ten-row offline matching
- \`varyn/agent_mode_gui.py\`: manual read/review/import and owner-supplied results
- \`tests/test_owner_billing_reconciliation.py\`: adversarial no-network cases

### Verification limits

CI uses a simulated provider transport and mock public GitHub response.
The full owner-PC real-API-key, provider-side billing evidence and original
invoice authenticity are **NOT yet verified**. This change creates the
correlation mechanism that can accompany real acceptance testing.

A quoted total ceiling near $0.10 is still an ESTIMATE, not a provider
spending guardrail. Provider-account usage, live pricing and cost caps must
be verified separately before allowing any unattended paid calls.

No background daemon, production deployment, main merge, or signed Windows
release is performed by this PR.
