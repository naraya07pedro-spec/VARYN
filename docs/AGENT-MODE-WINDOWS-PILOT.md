# VARYN Public GitHub Agent: owner-facing Windows pilot

This stage exposes a **Read-only GitHub agent** control inside VARYN Chat.
It builds on the verified execution library and reflection foundation.

## What is user-accessible

- Choose OpenRouter/DeepSeek and configure the reviewed model and prices
  using existing VARYN chat controls. API keys remain in the existing local
  process session or owner launcher environment, not in the agent database.
- Open **Public GitHub agent**, enter a short task, and explicitly enable a
  single GitHub public metadata read. The option is OFF by default.
- Independently opt in if public metadata may be sent in the second model
  request. This also defaults OFF.
- Every model request and tool dispatch uses the pre-existing exact-content
  desktop approval modal. All Tk approval dialogs run on the GUI thread;
  network and model calls run in a worker thread.
- The worker uses UniversalGateway plus PublicGithubToolGateway. No direct
  raw model call is made outside those existing adapters.
- Closing the window denies pending approvals and revokes tool results.
  Already-sent HTTPS requests may still complete and may incur charges.
- The metadata-only journal lives in the local VARYN application folder.
  In-flight uncertain calls are not replayed after interruption.

## Explicit limitations

- Not a full autonomous agent or always-on scheduler.
- Public GitHub metadata only: cannot read private repositories, write to
  GitHub, send email, access browser cookies, or execute arbitrary tools.
- No live account acceptance has been performed by CI. The GUI integration
  is verified with native Tk smoke checks, but user-PC approval, signing
  requirements, pricing and provider account authentication remain unverified.
- This mode does not automatically invoke the reflection worker. Verified
  task outcomes and declassified lessons still require an independent host
  validation path before autonomous skill improvement can become trustworthy.
- The gateway cost ceiling is a **local estimation filter** of USD 0.10 per
  model request, not a provider-enforced billing cap.
- The current GUI strings are an English-first experimental pilot and have
  not yet been migrated into the 4-language translation catalog.

## Verification

- Windows: native ConsumerWorkspace Tk widget smoke, offline default and
  denial before any provider/tool dispatch.
- Ubuntu and Windows: bounded agent loop, learning kernel, reflection worker
  unit tests using mocked provider and public GitHub responses.

This PR is stacked on the previous three draft PRs. It neither merges those
PRs nor changes main directly.
