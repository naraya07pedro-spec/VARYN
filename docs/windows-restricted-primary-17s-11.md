# VARYN 17S-11 | Suspended Windows restricted-primary-token launcher

Date: 2026-11-05. This is a native **process-start isolation engineering checkpoint**, not proof that production VARYN's public GitHub adapter or private-file access is sandboxed. The code is not wired into the production request path yet. PR #1 stays draft, main untouched.

## Implemented

- \`varyn/windows_restricted_primary.py\` uses OS-issued \`CreateRestrictedToken\` and \`CreateProcessAsUserW\` to start a trusted Python executable with its **restricted primary token from process creation**, not a post-start impersonation shim.
- The process starts **suspended**. The host verifies \`IsTokenRestricted\` and inspects \`TokenRestrictedSids\` on both supplied and **actual child** primary token before returning its process object. It exposes a thread resume method to be called only *after* existing native \`WindowsChildJob\` attaches and enforces Low MIC, memory limits, one-process limit, matching owner SID and kill-on-job-close. Failure refuses the process; there is **no fallback to normal Popen**.
- The process starts with \`bInheritHandles=FALSE\`, no stdin/stdout handles, and a minimal environment containing SystemRoot only. It cannot yet carry real tool requests or return model data. A private-file synthetic proof is run via bounded process exit codes.
- \`tests/test_windows_restricted_primary.py\` creates a test-only user-readable file, then asks a real restricted-primary-token child to re-open it, rejecting a result if readable. It also checks an absent-file control and refusal to launch an untrusted executable or working directory. Ubuntu explicitly cannot claim the native Windows result.

## Failure mode identified by hostile testing

An initial genuine Windows CI run on commit \`879813d767dd471f0ccd739618a81ee617cdefcf\` **failed two tests**: the restricted Python child exited with OS status \`0xC0000142\` (DLL initialization failure), before its Python test could run. This is a real runtime compatibility failure, **not** successful read denial. The failure is retained at [CI #41884799572](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41884799572).

The original restricting SID was \`S-1-5-12\` (NT AUTHORITY\\RESTRICTED). A later experiment uses \`S-1-5-11\` (Authenticated Users) as a compatibility-first *weaker* restricting SID. This allows access to objects granted Authenticated Users and **cannot establish universal read isolation of all private files**. Its success still requires the native synthetic file denial test. No change grants private-file or mutating tools, and no previously unverified protection is claimed. A production-grade design needs a dedicated runtime image/dependency ACL allowlist and stronger restricted SID, with owner-device verification.

## Required gates

1. Both Windows and Ubuntu GitHub Actions must PASS on exact final HEAD, with native Windows read-denied and absent-file controls actually executed, not skipped.
2. A later milestone must implement a bounded, authenticated parent-child tool transport with strict inherited-handle allowlisting, plus execution of the **real** fixed GitHub metadata child under a restricted primary token and no insecure fallback.
3. Demonstrate safe startup of the genuine bundled executable, Python libraries, and approved tool source on owner's Windows machine. Private files that contain ACEs for groups such as Authenticated Users may remain readable in the compatibility design.
4. Keep the production \`ProcessRepoFetcher\` reporting \`os_sandbox=False\`, \`windows_mic_blocks_private_reads=False\` and disallow private/mutating tools until the boundary truly holds.
5. Consumer ChatGPT/Claude/Gemini official-app sync Option C remains an explicit unmet objective; this local Windows work does not replace it.

Primary sources:
- https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken
- https://learn.microsoft.com/en-us/windows/desktop/api/processthreadsapi/nf-processthreadsapi-createprocessasuserw
- https://learn.microsoft.com/en-us/windows/win32/procthread/creating-processes
- https://learn.microsoft.com/en-us/windows/win32/secauthz/restricted-tokens

Next: reconcile native Windows CI, then implement safe transport and actual restricted primary-process use in the production public tool. Do not merge the draft PR.
