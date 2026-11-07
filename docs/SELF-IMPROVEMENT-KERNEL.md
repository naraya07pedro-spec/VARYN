# VARYN Learning Kernel: evidence-gated procedural improvement

This milestone adds a **standalone local learning primitive**, not Hermes parity.
It does not train model weights, auto-run tools, connect to chat/Telegram,
schedule reflection, rewrite Python code, or access third-party accounts.

## What exists

- Task outcomes stored as metadata with hashed task IDs and SHA-256 receipts.
- Candidate skill text requires two distinct successful, host-verified outcomes.
- Comparisons use 5-40 unique held-out cases and a **trusted host evaluator**
  scoring both current and candidate instructions on the exact same cases.
- Candidate auto-promotion requires at least one newly passing case and **zero
  previously passing cases becoming failures**. Rejected candidates do not
  replace working skills. Stale promotions fail closed.
- Previously accepted skill versions can be restored, with a metadata audit log.

## Critical trust boundary

A \`verified_by_host=True\` flag is a caller assertion, not authentication.
A model-controlled caller can fabricate receipts. A model's own evaluation
scores are not objective ground truth. Only an independent trusted host
running a protected test suite should call evaluation/promotion.

Skill text is untrusted data and cannot grant new tool permissions.
The SQLite file is **not encrypted**. Do not store secrets, personal
conversations, customer data or private paths in skill text.
No provider calls or filesystem access beyond the explicitly chosen local
SQLite file are performed.

## How to test

\`\`\`bash
python -m unittest discover -s tests -p 'test_learning_kernel.py' -v
\`\`\`

Tests use synthetic data and a deterministic judge. They demonstrate that
the state machine rejects regressions, not that a real AI has improved.

## Integration needed before claiming autonomous learning

1. A genuine bounded model-planning -> tool-call -> observation -> verified
   task-result loop, linked to VARYN's existing approval and recovery controls.
2. Host-owned, evidence-backed task completion receipts and privacy controls.
3. Skill generation/reflection constrained to low-trust candidates.
4. Independent, hidden, outcome-based evaluation, canary selection, rollback.
5. Opt-in background scheduler with cost caps and access scopes.

The existing \`main\` branch and production deployment remain unchanged.
