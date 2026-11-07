# Stage 8: Redacted acceptance receipts for real model evaluation

Stage 8 adds **inspectable quality evidence** to the manually approved Stage 7
Windows evaluation. It does not claim production improvement or real provider
account acceptance until the owner runs an authorized session on their own PC.

## New results after an evaluation

The Windows Public GitHub agent displays actual independently checked
**baseline successes, candidate successes, test-case count, and regressions**.
The local "Last evaluation receipt" button shows the persistent session
summary even after application restart.

The local SQLite database under
\`%LOCALAPPDATA%\VARYN\learning.sqlite3\` stores:
- one random per-session ID and UTC timestamps
- status (completed, rejected, declined, needs_review, interrupted)
- provider name and a SHA-256 digest of the configured model ID
- max quoted **estimate** in micro-USD, NOT actual provider billing
- number of approved public tool reads and attempted model calls
- number of successful responses versus failed/uncertain calls
- counts of provider-reported input/output tokens and responses missing usage
- five held-out case count, baseline and candidate correctness, regressions
- SHA-256 of the actual public-case observation set, and a local checksum
  of the summary record

It **does not store** raw model replies, benchmark prompts, API keys,
private documents or owner task content. Raw public case data are hashed.
The stored model ID is hashed; note that small dictionaries of possible
model IDs can be guessed offline. SQLite storage is **not encrypted**.

## What the evidence does and does not prove

A local checksum detects accidental local corruption, not a malicious
user who can modify both database and checksum. A verified provider
model string is the upstream response's claim, not cryptographic
attestation of model weights. Provider token usage may be absent or
incorrect. Evaluation data are five public GitHub metadata observations,
not a broad reasoning-quality benchmark.

**Actual provider billing remains UNKNOWN.** The estimated spend ceiling
is only a local calculation from a user-reviewed model quote. The gateway
does not check provider invoice, account balance, input-token upper bound,
provider-side spending limit or any cross-process costs. Each real
request still requires one explicit, fresh desktop approval. No background
polling or automatic live evaluator is enabled.

A completed result is stored only with five public reads, ten attempted
model calls, five evaluated cases, and a consistent score matrix.
A revoked request, provider failure, unexpected/missing provider-reported
model identity, or crash will **not** be represented as a successful run.
An interrupted session can remain marked running_or_interrupted; no
automatic retry or false promotion follows.

## Independent test scope

The CI suite uses real VARYN gateway and SQLite APIs, but synthetic
model HTTP replies and synthetic GitHub metadata:
- verifiable persistent 4/5 baseline versus 5/5 candidate quality
- usage counters from the isolated evaluation callback, not unrelated
  Chat requests sharing the same global UsageBudget
- no approval, denied public read, denied model call, missing upstream
  model identity, restart, tamper detection and impossible score matrices
- previous Windows Tk, backend and packaged EXE acceptance

No API key is present in CI and no real provider charges are incurred.

## Owner acceptance on the real PC (not yet executed)

Download the unsigned preview built from this branch's CI artifact.
Verify its manifest. Configure a reviewed live model and key in Chat.
Run a short, explicitly approved public-facts task to collect legitimate
evidence, then use readiness and start a separately approved evaluation.
Confirm the five public reads and ten model calls, inspect both scores
and the persistent local receipt, and compare provider-side actual
charges manually against the estimate. Stop if the provider identity
is missing/mismatched, usage is unreported, or the receipt is corrupted.

Do not disable Windows security to run unsigned code. There is no
automatic production deployment or official signed release.
