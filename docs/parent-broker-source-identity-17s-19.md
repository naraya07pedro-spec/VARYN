# VARYN 17S-19 | Synthetic parent broker source-identity hardening

Date: 2026-11-05. Status: **implementation committed, CI verification pending**. This is still a CI-only synthetic security gate, not owner consent, general file access, or production AppContainer isolation.

## Change
- Reject source files with multiple hardlinks at metadata preview. This is a defensive restriction for the single fixed synthetic fixture, not a full native Windows reparse-point or handle safety proof.
- Bind preview and dispatch identity to device, inode, size, mtime_ns, **ctime_ns and link count**, instead of only the first four fields.
- Check fstat identity again **after** the bounded source read; mutation detected at that boundary refuses the request before journal claim or child creation.
- Add adversarial tests for hardlinked fixture and mutation after bytes are read. Tests assert no durable claim is created for either refused source.

## Residual threats
- The source is deliberately disposable and synthetic. Even double metadata checks cannot prove byte-stable content against an attacker that can alter and restore metadata, or against a file mutation invisible to the platform's stat fields.
- Windows directory/root reparse substitution, multi-thread concurrent approval, full handle-table audits, production cancellation, and actual human GUI consent remain unproven.
- A post-read failure burns this in-memory authorization. Production-safe files must use stronger handle-anchored checks and an explicit owner approval UI before enabling private resources.
- The official ChatGPT, Claude and Gemini consumer-app two-way sync **Option C** remains unmet.

## Verification gate
Run `python -m unittest discover -s tests -p "test_parent_synthetic_read_broker.py" -v` and all Windows/Ubuntu CI before calling this checkpoint verified. Record the exact HEAD and CI URL in PR #1. Leave PR draft and main unchanged.
