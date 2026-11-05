# VARYN 17S-15 | Durable parent claim journal + Windows kernel pipe identity; AppContainer LOCAL namespace blocker

Date: 2026-11-05. Status: **durable synthetic dispatch journal verified; native same-user Windows pipe PID attestation verified; AppContainer-to-host named-pipe attachment BLOCKED on hosted Windows.** This is not a production private-file sandbox, broker IPC, or automatic AI-consumer-app integration. PR #1 remains OPEN / DRAFT to \`main\`.

## Engineering decision and threat model

The 17S-14 CI-only broker used a shared profile-owned file and a child-readable HMAC key. While the one-request/one-response handshake and synthetic read denial passed on a real AppContainer, a compromised child could also read the HMAC signing key and sign arbitrary results. This is insufficient for production trust. A production broker must bind permissions to an **actual Windows process identity**, keep authorizing secrets in the trusted parent and prevent crash-triggered replay.

17S-15 adds two independently verified building blocks and tests the interaction with a real zero-capability AppContainer. Avoid conflating each proof with the incomplete end-to-end system.

## Delivered

### 1. Parent-owned crash-safe SQLite claim-before-dispatch

- \`varyn/durable_broker_journal.py\` owns a parent-side SQLite database with \`WAL\`, \`synchronous=FULL\` and \`BEGIN IMMEDIATE\` transactions. It writes \`claimed\` and COMMITs **before** the child can be dispatched. Duplicate request IDs are rejected across multiple open connections and after database close/reopen. A claimed request that never completed is deliberately **not** automatically replayed. It may transition once from \`claimed\` to \`completed\` or \`failed\`, with no retry through an existing ID.
- The table stores only SHA-256 digests of 128-bit request IDs, status, claim timestamp and completion timestamp. No conversation text, provider credentials, file paths, prompts, request payload, model output or HMAC key are saved. Missing/invalid IDs and bad timestamps are refused.
- \`tests/test_durable_broker_journal.py\` verifies persistence, crash-style reopen, multiple DB connections racing to claim the same ID, exact one-time state transitions, corruption refusal and no sensitive payload columns. Hosted Windows and Ubuntu tests passed.
- The CI-only existing 17S-14 AppContainer file broker now uses the journal in an owner-private **disposable host-side temporary directory**: claims the signed request ID **before** \`CreateProcessW\`, then marks it completed only after the parent validates the child's response. This demonstrates correct ordering. It is not an owner-installed long-lived journal and does not grant any production tool permission.

### 2. Native Windows local named pipe, OS-issued peer PID

- \`varyn/windows_pipe_identity.py\` creates a random, unique, one-instance, local-only \`LOCAL\` named pipe; uses an explicitly protected SDDL DACL for SYSTEM and the current Windows user, with noninheritable server handle and \`PIPE_REJECT_REMOTE_CLIENTS\`. Overlapped connect/read operations have bounded waits and cancellation. \`GetNamedPipeClientProcessId\` supplies the client's **kernel-reported PID**, which must match the expected child process PID **before** any data is consumed. A wrong PID or repeated attempt burns the one-shot session.
- \`tests/windows_pipe_pid_client.py\` and \`tests/test_windows_pipe_identity.py\` demonstrate a real **ordinary Windows child** connecting to this pipe, with a negative test passing a forged expected PID and verifying refusal. This is a valid **OS peer-PID proof for an ordinary child**, NOT AppContainer identity.
- For the separate AppContainer experiment only, the pipe DACL can add the exact OS-issued profile SID, not an all-apps identity, Everyone or Authenticated Users. The package ACE grants only scoped file data read/write, metadata and synchronization rights using \`0x00120183\`; **not \`FILE_CREATE_PIPE_INSTANCE\` (0x4)**. The child requests \`FILE_WRITE_DATA\` only, not \`GENERIC_WRITE\`. The host additionally requires the PID to match its suspended, independently primary-token-attested AppContainer child.
- \`varyn/appcontainer_pipe_child.py\` is an offline fixed operation with an actual granted synthetic file read and host-only synthetic file denial *before* any attempted pipe connection. No real document, user prompt, provider call or network access.
- All native tests are hosted-Windows-only and only the CI AppContainer module creates/deletes a temporary profile. Ubuntu cannot attest Win32 behavior. Production \`ProcessRepoFetcher\` remains unchanged with \`os_sandbox=False\`.

### 3. Real AppContainer named-pipe attempt: BLOCKED

The first actual AppContainer pipe test [GitHub Actions #41966096822](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41966096822) on hosted Windows failed with a bounded connection timeout. We then made the child report only a coarse Win32 error category and the host expose only its exit code. [Red #41966433336](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41966433336) yielded child exit **\`0x5C\` (92)**, which the fixed child explicitly emits only for \`ERROR_FILE_NOT_FOUND\` or \`ERROR_PATH_NOT_FOUND\` when trying to open the pipe. This strongly indicates the AppContainer's \`LOCAL\` pipe lookup does not find the pipe object as created by the full-trust parent. This is **not** a confirmed ACL failure and is **not** a native OS-authenticated AppContainer IPC success.

The hosted Windows AppContainer pipe regression now marks ONLY this exact known namespace-missing error as **SKIP / UNAVAILABLE**, preserving failure for any other error. A SKIP is **not a security capability pass**. Native AppContainer 17S-13 read-denial and 17S-14 file-based broker tests remain independent and must continue to pass.

Microsoft documents AppContainer-specific namespace behavior for named objects and pipes. Merely adding the right package SID to a full-trust parent's pipe DACL is not guaranteed to bridge the AppContainer namespace. We will **not** grant all app packages or edit the host's ACLs to hide this failure.

## What is verified versus what is still missing

| Property | 17S-15 result |
|---|---|
| Durable SQLite parent-side synthetic claim/no-replay | Verified in Windows and Ubuntu tests |
| Ordinary Windows child connected and OS-reported PID matches | Verified native Windows |
| Forged expected PID rejected | Verified native Windows |
| Real AppContainer denied access to known owner-private synthetic file | 17S-13 and 17S-14 separately verified |
| Real AppContainer connects to host named pipe across \`LOCAL\` namespace | **NOT verified; child OS path missing (\`0x5C\`)** |
| Broker-held secret, OS-bound authenticated AppContainer request+response | **NOT implemented** |
| Production Job Object, termination/cancellation, secure owner-PC acceptance | **Not completed** |
| Official ChatGPT/Claude/Gemini consumer app two-way sync (Option C) | **Not verified/available** |

## Next technical gate: stop fighting namespace, use an explicit kernel handle grant

Microsoft recommends \`STARTUPINFOEX\` with \`PROC_THREAD_ATTRIBUTE_HANDLE_LIST\` when a child must inherit only specifically approved handles. The next experiment should deliver two **new, anonymous pipe handles** (one input, one output) solely to the already-attested AppContainer child and no other inherited handle, with \`STARTF_USESTDHANDLES\` and \`bInheritHandles=TRUE\` only alongside the handle allowlist. The owner must still verify the child primary AppContainer token before resuming; close unused ends in the parent immediately, use bounded I/O and job limits, keep real files out, and require both a valid synthetic request/response and the known-present denied-file control. This is an **alternative proof to attempt**, not a claim of supported or working containment.

Also add a persistent user-approved parent broker journal, explicit cancellation and no replay, reviewed file grants and owner-device acceptance before considering any private or mutating tool. Audit all inherited handles, Win32 permissions and side channels with an adversarial model.

## Primary documentation

- [Microsoft CreateNamedPipeW](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-createnamedpipew)
- [Microsoft GetNamedPipeClientProcessId](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid)
- [Microsoft Windows AppContainer named pipe restrictions](https://learn.microsoft.com/en-us/windows/apps/develop/communication/interprocess-communication)
- [Microsoft explicit handle-list inheritance](https://learn.microsoft.com/en-us/windows/win32/procthread/inheritance)
- [Microsoft CreateProcessW security remarks](https://learn.microsoft.com/en-us/windows/desktop/api/processthreadsapi/nf-processthreadsapi-createprocessw)

Final CI on the last exact SHA must be verified and appended as a PR comment. A green baseline containing skipped AppContainer IPC is NOT proof of production-ready broker identity.
