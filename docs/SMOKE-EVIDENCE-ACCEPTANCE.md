# Stage 11: Hardening owner smoke evidence and testing one real GitHub GET

This stage addresses factual-evidence shortcomings in Stage 10, rather
than claiming an unavailable real OpenRouter/DeepSeek account test.

## What was fixed

1. After a consent-gated public GitHub GET, the fixed five-field
   observation is hashed **before** any model request. The same public
   observation SHA-256 now persists for verified success, factual mismatch,
   denied model request, and an uncertain model response. This lets the
   owner distinguish an absent public result from a model disagreement.
   Prompts, full GitHub response and model text are still not stored.
2. The smoke recorder's private terminal transition refuses
   \`verification_passed\` without a validated claim from the existing
   deterministic verifier tied to the exact observed data hash. It also
   refuses \`verification_failed\` without a source observation digest.
   These are host-code assertions, NOT authentication of arbitrary callers.
3. \`acceptance_gate(record)\` recomputes the complete local receipt
   digest before any classification. A caller cannot simply relabel an
   injected test transport as real with the old digest and leave the
   acceptance classification unchanged.
4. Offline Windows "Last provider smoke receipt" shows a cautious
   evidence category. Simulated/custom transport is marked as such.
   A completed test with the configured network adapter, provider-reported
   response ID, token usage and correct fact copy becomes ONLY
   \`owner_live_candidate_needs_provider_account_check\`, not production
   accepted or provider-attested.
5. A separate CI job performs exactly ONE genuine anonymous public
   GitHub GET through VARYN's existing fixed-host, no-token, no-redirect
   \`PublicGithubToolGateway\`. If successful this verifies the live
   GitHub **read-only tool path** and prints a digest of five public fields.
   No paid model is involved. A failed job is real negative evidence,
   not silently treated as success.

## Trust and cost limits

- A successful real public GitHub GET from a GitHub-hosted runner is
  independent evidence that the public adapter worked at that time,
  **not** that it works from the owner's Windows PC or local network.
- CI model results are simulated using injected HTTP transports.
  They do not verify provider keys, models, actual pricing, bills, token
  accounting, genuine model improvements, or native consumer-app sync.
- The label \`configured_network_adapters\` is local configuration
  provenance, not proof of authenticated account use or a signed provider
  response. A local DB writer can replace both receipt and hash.
- Smoke remains one public GitHub GET and at most one explicit reviewed
  AI request. Request/token reservations are local. No new background
  task, automatic retry, account-level spending cap, 24/7 deployment,
  native model account sync, GitHub mutation or private repo access.
- **No API key** is placed into CI. The owner must personally run the
  Windows preview with their own reviewed OpenRouter/DeepSeek route,
  approve the public read and exact AI prompt, inspect the receipt, and
  reconcile billed usage from the authenticated provider account.

## CI

- New hardened smoke tests (Ubuntu and Windows)
- One actual anonymous GitHub public API request (Ubuntu)
- Stage 10 owner-provider acceptance tests (Ubuntu and Windows)
- Native Tk Windows GUI test
- Existing benchmark, receipts, budget and grounding checks
- Unsigned Windows portable EXE build and frozen GUI smoke

The stacked PR remains draft and does not merge to main.


## Safely share a result for independent review (new)

On the owner Windows PC, in **Public GitHub agent**, choose **Copy safe
diagnostic summary**. This reads the latest local smoke receipt and
copies a fixed redacted JSON status to the Windows clipboard; it does
**not** make a network request or spend provider tokens. The user can
then choose to paste the result into a support conversation.

The summary contains only an allowlisted provider name, local source
category, attempted request counts (0 or 1), result of the local fact
comparison, whether upstream response ID and usage counters were
reported, and explicit **NOT independently verified** flags. The
clipboard text never includes model/response/session hashes, exact
timestamps, money, local file paths, private messages, model responses,
prompts, raw request IDs, credentials or provider account information.

If no run exists, the summary says \`no_receipt\`. If local integrity is
missing, changed or unverified, evidence details are withheld and the
report says \`receipt_untrusted\`. A synthetically run model can never
become an authenticated provider result merely by pasting the JSON.

The clipboard is a shared OS resource and other local apps may be able
to inspect it. The summary minimizes data, but the owner still decides
whether and where to paste it. Never share the original local SQLite
database, API keys, screenshots containing credentials or complete
provider invoices to request troubleshooting assistance.

**Crucial limit:** the copied summary provides a route for discussing
the owner's local test. It is not a signed provider receipt, independent
proof that the model ran on a paid account, a spending cap, or authority
to merge the draft PR stack.
