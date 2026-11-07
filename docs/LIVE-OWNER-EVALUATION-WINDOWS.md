# Stage 7: Owner-reviewed LIVE evaluation from Windows

This stage connects the Stage 6 BudgetedReflectionScheduler to VARYN's
existing real OpenRouter/DeepSeek gateway and read-only public GitHub tool.
It is a **manual, host-reviewed evaluation session**, not an unattended
background agent or proof of learning on other kinds of tasks.

## How the owner can use it

1. Open VARYN Windows Chat, configure a reviewed OpenRouter or DeepSeek
   model ID, quote and local API key. Confirm the existing online session
   permission. No API key is stored in the learning database.
2. Open **Public GitHub agent** and select **Check learning readiness**.
   The check is offline. Learning requires at least two different
   fact-match success receipts, one previously recorded factual mismatch,
   and ten available reservations in the app's shared model budget.
3. Enable **Allow 5 public GitHub reads + 10 reviewed AI calls**.
4. Select **Run live learning evaluation** and inspect the summary:
   five fixed public repos, ten potential model requests, token budget and
   total *estimated* micro-USD cost. This is NOT a billing ceiling.
5. Only after owner session approval, the worker may propose up to five
   public GitHub metadata reads (python/cpython, pallets/flask,
   django/django, psf/requests, github/docs). The user reviews EACH read.
6. Once five genuine validated public observations are collected,
   the existing scheduler atomically reserves 10 evaluator calls and
   compares the previous skill with a host-controlled candidate across
   the identical five cases. Each real model call must pass another
   exact outgoing-prompt owner review. The model returns structured facts,
   and the host checks every field against the corresponding observation.
7. Promotion requires at least one additional correct case and zero
   previously-correct regressions. Any failure, denial, or uncertainty
   retains its reserved budget and is never auto-replayed.
8. The new scheduler preflight prevents fetching new public cases when
   the same evidence batch is already processed or daily quota exhausted.

## Operational and trust boundaries

- **Maximum outbound calls for one approved session:** five public GitHub
  reads plus ten model requests. Each action has fresh owner consent.
- Existing VARYN shared UsageBudget must have 10 remaining requests and
  2560 reserved output tokens. It is process-local, not a durable
  provider-side quota.
- A separately reviewed local price snapshot gates the run. The example
  total estimate limit is 100000 micro-USD (~US$0.10), not a guarantee
  about actual billing, billing errors, retries outside VARYN, input token
  truncation, fees or provider account spending. The provider's actual
  bill is neither read nor enforced here.
- No private repository access, GitHub writes, shell execution, model
  self-granted permissions, or API keys sent to the benchmark prompts.
- The model's evaluation runner is fixed to the owner-selected model,
  and gets only five public metadata scalars per case plus a bounded
  lower-trust skill reference. It cannot choose its own cases or grades.
- The proposing reflector remains a **fixed conservative text**. This
  does NOT generate novel lessons from open-ended conversations or
  dynamically fine-tune model weights.
- No new standalone system service, daemon, Windows Task Scheduler entry,
  VPS deployment, or live provider credentials are installed automatically.
  The process runs only during a manually authorized session.
- No real owner-account acceptance was performed in automated CI. Tests
  simulate the official provider JSON response shapes and public tool
  adapter through deterministic local transports. The frozen EXE smoke
  only checks offline startup and integrity.

## Recovery

An interruption during evaluation is marked needs_review by the durable
scheduler. The same batch cannot be automatically repeated, even after
restart or on a later day. No user prompts, secret API keys or benchmark
private contents are recorded by the scheduler ledger.

## Exact tests

    python -m unittest discover -s tests -p "test_owner_live_evaluation.py" -v
    python -m unittest discover -s tests -p "test_feedback_evaluation_scheduler.py" -v
    python -m unittest discover -s tests -p "test_grounded_learning_bridge.py" -v
    python -m unittest discover -s tests -p "test_consumer_workspace_tk.py" -v

The suite tests cancellation before dispatch, exact call limits,
exhausted budgets, genuine-gateway-shaped requests, factual mismatch,
no-regression rejection, durable crash recovery and default-off GUI.
