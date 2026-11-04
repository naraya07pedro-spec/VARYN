# Checkpoint 17F: Synthetic-only desktop file access guard

**Date:** 2026-11-04 (Asia/Jakarta)  
**Status:** Implemented on draft PR #1; CI outcome recorded in docs/progress-log.md.  
**Scope:** Offline desktop file demonstration. No private, client, financial, browser, provider-account or cloud-drive data.

## Security issue found

17A–17E repeatedly instructed the user to choose *synthetic files only*, but the desktop actually called tkinter.filedialog.askdirectory(), which could select **any folder** readable by the user's account. The Python ScopedFileGrants caller only asserted user_confirmed=True; it was not an authenticated Windows permission prompt and not a process sandbox. A documentation warning was not a real restriction. Genuine user files could therefore be inspected through the same experimental code path if the user selected an inappropriate folder.

## Implemented 17F boundary at the desktop UI

1. Removed desktop's arbitrary folder-picker call. The desktop never asks the user for a filesystem path for its file demonstration.
2. The desktop still requests explicit Yes/No permission, but the permission now specifies that VARYN will create **exactly two fixed synthetic UTF-8 files** in a fresh randomized TemporaryDirectory owned by this VARYN process: sample.txt and notes.md.
3. Only that freshly constructed temporary directory is passed by the trusted desktop code to ScopedFileGrants. The existing bounded metadata-only filename count, five-minute lease, ten-operation quota, native Windows handle-relative opens, fail-closed timer, and file-content non-upload assurances remain in force.
4. Declining the prompt creates no directory or grant. Failure to create the fixture or grant permission cleans the candidate directory. Replacing a grant revokes the old grant then deletes the old sample folder. Explicit revoke and desktop close release the grant first, then clean up only the VARYN-created fixture. On attempted inspection after expiry/denial, the desktop revokes the remaining handle (if any) before cleaning the sample.
5. Desktop UI buttons now explicitly describe a generated demo folder rather than suggesting an arbitrary existing folder. Neither filenames, paths nor contents are appended to the chat transcript.
6. The underlying Python ScopedFileGrants API remains available to trusted host code for separate synthetic tests. This **does not** make same-user Python code, a compromised desktop process or the OS itself incapable of opening files. No new Windows security token, protected process, OS sandbox, or fully authenticated human identity was created.

## Inspectable source and tests

- varyn/synthetic_fixture.py: fixed sample generation, ownership and idempotent cleanup.
- varyn/desktop.py: consent-first synthetic-only grant and teardown, no askdirectory.
- tests/test_desktop_file_scope.py: **13 headless UI wiring tests**, replacing the prior 11: consent/decline, no picker calls, outside-folder privacy, failures, counts, replacements, expiry, revoke and window close.
- tests/test_synthetic_fixture.py: **4 new filesystem tests** for fixed content, idempotent deletion, noninterference with neighboring files and cleanup after simulated failed creation.
- .github/workflows/memory-checks.yml: explicit Windows and Ubuntu regression steps for desktop synthetic-only UI and fixture cleanup, in addition to the complete suite.

## Important limitations

- **No OS-enforced security isolation:** a malicious process with the same Windows account privileges can access files independently of VARYN. The code-level restriction only limits VARYN's desktop demonstration pathway; the permission flag is still a trusted-caller assertion.
- **Not an immutable sample:** another local process could modify the generated sample while VARYN is running. The existing native read checks only mitigate detectable changes.
- **On-disk fixture lifecycle:** revoked/replaced/closed/inspected-expired samples are cleaned normally. A timed-out permission closes the OS handle even while idle (17E), but the two benign sample files can remain until the user interacts with the desktop or it exits. Abrupt process death may leave temporary samples. Do not claim guaranteed crash cleanup.
- **No actual owner's PC acceptance:** CI validates Python and native Windows behavior in GitHub-hosted runners, not clicks, power-loss recovery, antivirus restrictions or filesystem peculiarities on the owner's device.
- **No real official-app synchronization:** Option C remains using official ChatGPT/Claude/Gemini apps with future automatic two-way conversation/context sync. A model API or local chat history is not a substitute, and no such connector was introduced.
- **No real user folders:** neither private documents nor password/configuration directories should enter this experimental demo. Future genuine file access requires a separate threat model, permission architecture, OS process separation and physical Windows acceptance before re-enabling a picker.

## Synthetic-only manual acceptance steps (not yet executed on owner's laptop)

1. Launch the source-only desktop after checking its integrity, with Python 3.12 and Tkinter.
2. Click **Create & grant VARYN demo folder**. Declining should create nothing.
3. Approve and inspect. The displayed result should count exactly two generated sample files, with no names, paths, or content in chat.
4. Revoke and inspect again. The old permission should not work.
5. Repeat, then close and restart. The old permission must not persist.
6. Never select or import a real folder: this UI intentionally does not offer that action.

This checkpoint makes the demo scope match its documented data-handling policy. It is **not** evidence that VARYN is ready to handle sensitive files, nor a substitute for the unchanged official-app sync requirement.
