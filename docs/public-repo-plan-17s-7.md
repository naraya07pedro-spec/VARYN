# VARYN 17S-7 | First reviewed two-step external tool workflow

Date: 2026-11-04. This is a bounded **public GitHub repository comparison**, built on the existing 17S-2 through 17S-6 security gates. It is not autonomous model planning, private-file access, an OS sandbox, or official consumer-chat synchronization.

## Problem solved

Earlier 17S-2 through 17S-6 work provided a one-request public GitHub metadata tool with separate explicit permission, a supervised short-lived child, native Windows Job Object, Low MIC and stale-result suppression. It still did not perform a useful *multi-step* user task. This checkpoint adds a simple end-to-end workflow: **read two distinct public repository metadata records, one by one with separate human consent, and compare exact structured fields locally**.

## Accepted plan, exact schema

User-supplied or untrusted model-produced plan text can be staged, but cannot self-approve:

```json
{
  "format": "varyn.public_repo_comparison.v1",
  "repositories": [
    "naraya07pedro-spec/VARYN",
    "python/cpython"
  ]
}
```

Only that exact top-level schema is accepted. Exactly two distinct `owner/repo` names are required; duplicate JSON keys, URLs, extra fields, unsupported tool names, oversized input, duplicate targets, ambiguous paths and unexpected values fail closed. The model is not a trusted approver.

## Owner action and execution chain

1. On desktop, enable the **GitHub-specific** public metadata network checkbox, independently of any AI-provider API checkbox.
2. Paste the exact JSON plan into the prompt field and click **Review 2-repo public GitHub comparison plan (JSON)**. A first dialog previews both approved targets plus the unique plan digest, without opening any network connection.
3. If the owner approves this two-step task, a **second, separate dialog** previews the first exact one-use GitHub metadata GET endpoint and digest. Denial stops the task; no request is sent.
4. After a successful, strictly sanitized first result, a **third, separate dialog** previews the second exact one-use GET and digest. Denial prevents the second network call. The task does not proceed or retry without consent.
5. Only when both safe, exact results arrive does VARYN display a **local deterministic comparison** of stars, GitHub open items including PRs, and archive flags. It reports which repository has more stars and the difference. **These numbers do not establish code quality, security, trustworthiness or suitability.** No result is sent to an AI model or persisted by this feature.

The existing fixed `https://api.github.com/repos/{owner}/{repo}` tool remains the sole network destination, with the 17S-6 child security gates on Windows. A comparison never grants arbitrary browser, shell, personal-file, private GitHub, mutating or credential operations.

## Revocation, crash and staleness

- The public network checkbox being turned off invalidates the pending review, the in-flight result, and the entire comparison. A pending next-step callback checks the exact plan object, so a cancelled task is never automatically resumed.
- The existing hide/cancel button discards the comparison, invalidates the in-flight result and attempts to terminate the child. An HTTP request already sent cannot be unsent.
- Closing VARYN discards any incomplete task. No startup replay, retry or persistent task credentials.
- A manual single-step GitHub read cannot steal the comparison worker while its plan is active. There is a strict one-in-flight request rule and a worker/gateway exact-identity gate.
- Complete result records are validated again before committing each step. Malformed or unexpected data cancels the whole comparison; the application never synthesizes partial results.

## Deterministic tests

- `tests/test_public_repo_plan.py`: strict parsing, rejection of tampered/duplicate keys and repeated targets, one-use plan review, separate per-step consent, third-dialog denial, no second call after revocation during in-flight first call, no raw response injection, no stale result reuse, and worker/gateway mismatch refusal.
- `tests/test_public_repo_plan_tk.py`: hosted Windows Tk real button invocation with **three separate approval prompts** and two mocked public repo GETs. It proves real GUI callback wiring without contacting GitHub or the model provider.
- `.github/workflows/memory-checks.yml`: explicit portable and hosted-Windows acceptance steps on top of all existing regressions.

## Nonclaims and known blockers

- **Not autonomous AI agent orchestration.** The plan format and two tool types are fixed and parsed locally; any untrusted AI-proposed text still requires manual review per step.
- **Not read isolation.** Windows Low Mandatory Integrity prevents many writes upward, but it does **not** prohibit reading accessible same-user private files. This feature introduces **no personal file input**. A genuinely read-restricted Windows AppContainer/restricted token/ACL broker remains a separate security milestone.
- **Not validated on the owner's Windows PC** and not live GitHub API connectivity proof. Hosted CI uses mocked network fetchers; actual external requests require explicit owner confirmation in the installed desktop.
- **Not official consumer-app history sync.** The exact user requirement of automatic two-way ChatGPT/Claude/Gemini *consumer application* conversation synchronization (Option C) remains externally blocked by unverified interfaces. A generic model-provider API or this comparison cannot replace it.
- Green unit and hosted Tk tests verify the implementation paths, not security against arbitrary malicious same-user code, not real-world app usage, and not completed owner acceptance.

## Acceptance gate

Before recording 17S-7 as engineering-valid, verify **exact final HEAD** has Windows and Ubuntu SUCCESS, test counts and skips, explicit new 17S-7 steps passed, PR #1 remains draft and `main` SHA unchanged. Record earlier red tests and corrections if any.

## Next valuable checkpoints

Validate on the user's actual Windows device, then add narrowly scoped owner-reviewed practical tool chains with deterministic reconciliation, bounded state recovery and explicit confirmation of each action. Progress toward real OS read isolation independently before allowing any personal files or unsandboxed plugins.
