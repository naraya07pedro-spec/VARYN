# VARYN 17S-6 | Windows Low Mandatory Integrity Control (MIC) gate

Date: 2026-11-04. This is a narrow, kernel-enforced Windows write-protection gate on the **public GitHub metadata child process**, not an AppContainer, a complete restricted access token, or human identity verification.

## Rationale

17S-5 established a supervised same-user Python child, native Windows Job Object, one process, 192 MiB process-memory cap, kill-on-job-close, and OS token user SID consistency. But a same-user child still inherited the normal integrity level and could potentially write to ordinary same-user files. 17S-6 reduces that specific risk through Windows Mandatory Integrity Control (MIC).

## Implementation

- `varyn/windows_child_job.py`: after a native Job Object has been configured, read back and attached to the child, the trusted parent opens **the child process's primary token**, requiring `TOKEN_QUERY | TOKEN_ADJUST_DEFAULT`. It invokes Windows `SetTokenInformation(TokenIntegrityLevel)` with the canonical **Low integrity SID `S-1-16-4096`**, then queries `GetTokenInformation(TokenIntegrityLevel)` to verify **byte-for-byte SID equality**. The trusted parent process's token is not lowered.
- The new kernel enforcement step runs **after Job attachment, before the reviewed tool intent is delivered over the child's stdin**. If token access, setting, read-back or job checks fail, WindowsChildJob closes the job and refuses the request. No fallback to an ordinary medium-integrity child.
- The ordinary production `ProcessRepoFetcher` cannot override the native Windows Job/MIC guard without also injecting a fake process in an offline test. `ProcessRepoFetcher.status()` explicitly reports the Low MIC requirement and that private file reads are **not blocked**.
- `tests/test_windows_child_job.py`: actual Windows child probes run with normal Python process and a temporary, synthetic, parent-created file. The parent attaches the real guard, then sends the path only for the **offline test**. The child must read the sample and fail to open it for modification; the parent confirms exact bytes remain unchanged. Separate failure injection confirms an unenforceable MIC kills the child before any tool intent is sent.
- `.github/workflows/memory-checks.yml` requires an explicit hosted Windows native 17S-6 checkpoint step; unit test discovery also runs on Ubuntu, where Windows-specific tests are intentionally skipped.

## Narrow security guarantee, and what this does NOT protect

- Windows MIC normally enforces **No Write Up**. A Low-integrity token cannot modify Medium-integrity objects even when its discretionary access-control list (DACL) would ordinarily allow the write. This increases defense-in-depth against accidental or malicious modification by the public GitHub child.
- **Low does not mean No Read Up.** The default Windows MIC policy permits reading ordinary Medium-integrity files when the DACL allows it. Same-user sensitive files may still be readable, so VARYN **must not run untrusted arbitrary plugins or private-file tools in this child**. Full isolation requires an appropriately configured AppContainer/restricted token/ACL broker, together with real OS testing.
- A low-integrity child may still have networking capabilities. Request intent remains restricted to one fixed public GitHub API endpoint with no credentials, redirects, proxy, recursive access or writes. The child is not trusted with provider API keys.
- Process creation, Python startup and initial trusted imports occur **before** the parent attaches the job and lowers the child token. The child blocks reading stdin until the guard succeeds; this is not a suspended creation or prevention of all possible pre-gate execution.
- The parent and child retain the same OS user SID, and explicit Tk confirmation is **not** authenticated human presence. The desktop/parent is not protected against malicious same-user processes or injection.
- OS MIC enforcement has no bearing on the user's fixed Option C requirement for automatic **bidirectional sync of official consumer ChatGPT/Claude/Gemini apps**. That requirement remains externally blocked, not replaced by API/model conversation aggregation.

## Evidence required before DONE

Windows runner: native job/SID/MIC readback tests, real write-denial probe, fail-closed denied-token test, and normal offline child handshake pass. Ubuntu: portable test suite passes, with Windows-only probes skipped. Verify exact final SHA and logs, count skipped tests and failures, keep PR #1 draft and main unchanged. Record any red CI attempts and never infer live GitHub HTTP, owner-PC performance or personal-file safety from synthetic testing.

## Microsoft primary references

- https://learn.microsoft.com/en-us/windows/win32/secauthz/mandatory-integrity-control
- https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-settokeninformation
- https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-token_mandatory_label
- https://learn.microsoft.com/en-us/windows/win32/secauthz/restricted-tokens

## Next stage

To safely support owner-selected personal files or mutating tools, build a **true brokered least-privilege filesystem boundary** using file-handle ACLs/AppContainer or independently verified restricted tokens. Do not infer read isolation from Low MIC. Separately work toward strictly reviewed, genuinely useful multi-step tool orchestration and owner-PC acceptance.