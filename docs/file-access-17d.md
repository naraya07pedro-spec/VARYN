# VARYN 17D | Read stability, expired capability cleanup, local-volume gate

**Checkpoint:** 2026-11-04 (Asia/Jakarta)
**Stage:** Synthetic-only privacy and local file-read hardening. Not a security certification.
**Product contract:** The selected Option C target, automatic bidirectional syncing of the official ChatGPT/Claude/Gemini apps, is untouched and not delivered by this checkpoint.

## Prior issues and changes

1. **Stale open handles.** In 17C, calling ScopedFileGrants.status() reported an expired grant as inactive but did not actually close its pinned directory handle; cleanup required a read/list attempt or explicit revoke. In 17D, status(), grant() and revoke() all sweep expired grants, closing their readers and recording limited metadata-only audit entries. No timer or background thread was introduced. **Idle handles are still not guaranteed to close at the exact expiry instant:** host activity or process shutdown is required.
2. **File changed during read.** The Windows native backend previously validated file size at open, then performed one bounded ReadFile without checking native metadata after. In 17D it uses GetFileInformationByHandle before and after, compares volume, file identity, length, attributes, hardlink count and last-write FILETIME, and rejects short/long reads or a changed signature. A simulated concurrent append must not return mixed content. This is a best-effort change detector, not an atomic immutable snapshot. Same-size changes with unobservable/coarse timestamps, attacks by same-user processes, and all filesystem implementations are NOT proven safe.
3. **Unexpected remote or placeholder reads.** Approved Windows roots now require a normal drive-letter path for which GetDriveTypeW reports DRIVE_FIXED (3), refusing UNC, mapped remote, removable, unknown and other volumes. Native root and child handle metadata also reject OFFLINE, RECALL_ON_OPEN, RECALL_ON_DATA_ACCESS and REPARSE attributes. This is **conservative**, with no user override and no fallback to the old unanchored path. File cloud providers may still cause implicit remote activity during opening before attributes can be examined; these checks therefore **do not prove zero network usage** or turn the process into a sandbox.

## Files changed

- varyn/file_grants.py: opportunistic expired grant sweep and closing handles.
- varyn/windows_scoped_native.py: fixed-drive guard, remote placeholder attribute guard and pre/post native read signature checks.
- tests/test_grant_expiry_sweep.py: 6 synthetic cleanup tests.
- tests/test_windows_file_consistency.py: 7 tests (4 platform-agnostic volume/signature-policy cases and 3 live native-Windows cases).
- .github/workflows/memory-checks.yml: added an explicit Windows-only read-stability regression step, in addition to full Windows and Ubuntu unit suites.
- README.md, docs/progress-log.md: checkpoint and actual verified CI results.

## Primary reference documentation

- Microsoft: BY_HANDLE_FILE_INFORMATION fields, including size, link count and last-write FILETIME: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/ns-fileapi-by_handle_file_information
- Microsoft: GetDriveTypeW and DRIVE_FIXED vs DRIVE_REMOTE: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getdrivetypew
- Microsoft: FILE_ATTRIBUTE_OFFLINE, RECALL_ON_DATA_ACCESS and RECALL_ON_OPEN: https://learn.microsoft.com/en-us/windows/win32/fileio/file-attribute-constants

## Verification gates

Use synthetic temporary directories only. Tests require neither credentials nor model access and do not upload files to a provider.

    python -m unittest discover -s tests -p "test_grant_expiry_sweep.py" -v
    python -m unittest discover -s tests -p "test_windows_file_consistency.py" -v
    python -m unittest discover -s tests -v

In CI, the Windows-specific test module is explicitly rerun and its execution status inspected. Passing runner tests is NOT evidence of owner-hardware acceptance.

**Unresolved:** no human-identity authentication, OS process sandbox, isolation from malware running as same Windows user, guaranteed timer-driven expiry at the exact deadline, or authoritative official-app history connectors. Do not select real client, financial, confidential, password, browser profile or cloud-synced folders. Keep PR draft and main untouched until security gates and desktop-user acceptance are passed.
