# VARYN Checkpoint 17C: Windows native pinned-directory read prototype

**Date:** 2026-11-04 (Asia/Jakarta)
**Scope:** Native Windows NT object-relative file reads and handle-relative enumeration; synthetic test folders only.
**Risk classification:** Experimental; NOT an authenticated app sandbox, a production permission boundary, or approval to process private records.

## Why this exists

Prior VARYN Windows behavior used Python file opens on an absolute pathname after metadata validation. A malicious process with the same filesystem privileges might swap a root directory, reparse component or basename between the check and the actual open. Rechecking metadata reduces risk but does not make the check and the file open atomic.

Checkpoint 17C replaces **the Windows file-read AND directory-enumeration paths** with an intentionally narrow native-handle backend. The public ScopedLocalReader and the in-memory ScopedFileGrants remain the only host-approved call path for the desktop. They are still not exposed as agent/model tools.

## Actual behavior

- The trusted desktop host selects an existing absolute folder and separately obtains user confirmation; the previous 300-second / 10-operation grant limits stay unchanged. No model gets a folder path or grant token.
- VARYN opens that folder with Windows CreateFileW using read/list attributes, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, and FILE_FLAG_OPEN_REPARSE_POINT. It retains the directory handle until reader close, grant expiration upon use, revocation or quota exhaustion.
- At scope creation, it verifies native handle metadata, including directory type, absence of a reparse attribute, a single link, and a file ID consistent with the caller-selected directory. Existing ancestor checks remain.
- File content opens through **NtCreateFile** using OBJECT_ATTRIBUTES.RootDirectory pointing to that retained directory handle. The CreateDisposition is FILE_OPEN, with FILE_NON_DIRECTORY_FILE, FILE_OPEN_REPARSE_POINT and synchronous IO. No create/write/delete flag is requested.
- Top-level enumeration uses NtQueryDirectoryFile on the **same pinned handle**, not Python os.scandir(path). A bounded 2048-entry scan cap rejects oversized enumerations instead of silently showing arbitrary unbounded output. Each returned candidate is separately opened relative to that pinned handle and inspected before a filename is approved for a listing.
- Only top-level ASCII .txt/.md basenames, bounded sizes (default 16 KiB; at most 64 KiB), single-link regular files and strictly decodable UTF-8 without NUL are accepted. Reparse points, hardlinks, subdirectories, alternate data streams, reserved device aliases including NUL.foo.txt, and ambiguous trailing dot/space stems are denied.
- If native calls or validation fail, **access fails closed**. Windows never silently reverts to the former unanchored os.open(path) route.
- File contents are not copied to the desktop transcript, not uploaded to a provider, and not added to an agent tool catalog. The desktop only exposes a synthetic file count. No paid provider use or real app-history sync was performed.

## Evidence to inspect

Paths:
- varyn/windows_scoped_native.py
- varyn/scoped_files.py
- varyn/file_grants.py
- tests/test_windows_scoped_native.py
- .github/workflows/memory-checks.yml

The test suite includes **real Windows kernel calls on windows-latest**, not only mock metadata. It checks native read/list and close, hardlink refusal, symlink/referral refusal, rejected names/limits, no path-based fallback, and whether a still-pinned directory handle reads the original synthetic file after its pathname was replaced. A separate explicit Windows-only CI step reruns that test module to prevent unnoticed platform skipping. The CI run and complete head SHA are appended to docs/progress-log.md, not guessed here.

Microsoft primary sources:
- Native RootDirectory and FILE_OPEN_REPARSE_POINT: https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile
- File information via handle: https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex
- Windows reserved names and aliases: https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file

## Remaining gaps: no production-use claim

1. This is not process isolation: code running under the same Windows user may bypass Python grant objects entirely. Identity/authentication, least-privilege process boundaries, auditing and anti-tamper controls remain unimplemented.
2. Directory contents can change legitimately or maliciously *within* the approved directory. The anchored handle guarantees object-relative routing, not the provenance, consistency or trustworthiness of the bytes read. The prototype does not freeze a snapshot or solve concurrent writers.
3. Network-mapped volumes, unusual filesystems, Win32/NT edge cases, privileged tampering and all future Windows versions have not received comprehensive adversarial validation. A passing hosted Windows runner does not prove the owner's hardware configuration.
4. The desktop GUI folder-chooser and Yes/No confirmation have headless test coverage, not real human mouse-click verification on the owner's PC.
5. VARYN remains a standalone, non-production local-first prototype. No real ChatGPT, Claude or Gemini official-app history bidirectional synchronization is proven. The user's Option C requirement is unchanged.

## Safe local Windows acceptance steps (owner, synthetic only)

Use Python 3.12 with Tkinter and a disposable folder containing only self-created dummy .txt/.md files. Do not select Documents, Desktop, Downloads, browser profile, cloud-drive root, client/financial material or API-key directories.

    py -3.12 -m unittest discover -s tests -p "test_windows_scoped_native.py" -v
    py -3.12 -m varyn.doctor --json
    py -3.12 -m varyn.desktop

In the GUI choose "Grant synthetic test folder", approve the separate permission dialog, inspect the filename count, revoke and verify that another inspect cannot access the folder. Restart and verify the grant does not persist. These steps are **not yet recorded as passed on the owner's laptop**. Do not enable live provider connections for this acceptance check.
