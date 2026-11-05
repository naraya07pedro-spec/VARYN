# VARYN 17S-31 | Optional owner-approved local ZIP envelope inventory

Date: 2026-11-05. Experimental, privacy-first, fully **offline** metadata inspection of one *explicitly selected* exported ChatGPT/Claude ZIP. It is **not** a provider API connector, a chat-history reader, a ZIP extractor, a proof of genuine export or a solution for Option C automatic two-way consumer-app sync.

## Problem addressed

Stage 17S-30 introduced provider-supported, manual one-way **ChatGPT/Claude -> Gemini** migration through Gemini's official ZIP-import interface. However, the owner could not check basic archive shape before deciding whether to upload data to Google. Full parsing of private export history would create a significantly larger safety risk without proving provider access.

Stage 17S-31 takes the narrower first step: a **local envelope check** that inspects only ZIP entry metadata, prints nothing about personal chat titles or filenames, and does not unpack or parse chat messages. Importing remains entirely under the owner's control in the official Gemini interface.

## In-app workflow

1. Open the experimental portable VARYN app as an ordinary Windows user. In the 17S-28 official-app workbench, click `17S-30 | Official one-time ChatGPT/Claude ZIP import to Gemini`.
2. Choose the declared original source (`chatgpt` or `claude`). This is a **self-declaration, NOT authenticated provider origin**.
3. Click **`17S-31 | Inspect selected ZIP metadata locally (optional)`**. The first consent clearly says the pilot will see a transient selected path and only inspect the ZIP directory, with no extraction/upload. Denial means no file picker and no ZIP read.
4. If approved, a normal Windows file picker lets the owner select **one** ZIP from disk. The path remains only in a local function variable during this action, is not saved, sent or printed.
5. The second scrollable consent previews the exact scope: ZIP32 metadata, 128 MiB archive, 2 MiB directory, 5,000 entries; no chat body reads or Gemini upload. Denial, source change, busy/closing state or cancellation means no ZIP is opened.
6. If approved again, Python reads only the file's ZIP footer and central directory, validates bounds and metadata, and immediately closes the file. The in-RAM summary shows ZIP entry count, archive bytes and the **count of names matching known ChatGPT conversation-file patterns** (never the individual names). For Claude or unfamiliar names, it reports `zip_envelope_only`.
7. The user is free to **skip this inventory** and import the complete original ZIP directly into Gemini's own UI after separately reviewing Google's privacy/eligibility policy. A successful local inventory is **not** proof Gemini will accept/import anything.

## Explicit limits and defensive model

`varyn/native_export_inventory.py` has no HTTP, subprocess, external model provider API, SQLite/DB write, ZIP extraction, JSON parser or attempt to read an archived member payload. It does not call `ZipFile.open`, `read`, `extract`, `extractall` or `testzip`. It reads only a selected normal file in read-only mode after two GUI approvals.

Preflight rejects archives before the central directory can be allocated if compressed size exceeds **128 MiB**, ZIP32 footer is missing/ambiguous, directory metadata is over **2 MiB**, count over **5,000**, entries span multiple disks, ZIP64 sentinels appear or directory offsets are inconsistent. It then refuses encrypted entry flags, duplicate names, symlinks, absolute/traversal/ambiguous Windows paths, extreme declared expansion ratio or declared size above **5 GiB**. It doesn't extract any members even from a rejected ZIP. Normal ZIP32 exports with supported metadata pass.

These constraints are **deliberately stricter than Gemini's official 5 GB native ZIP upload limit**. Large legitimate archives, ZIP64, unusual/export-specific structures, or unknown future layouts may be refused. That is *not evidence* the archive is corrupt or Gemini-incompatible. The standard Python library's ZIP metadata parser is in-process and **not a hardened sandbox for adversarial files**. This pilot should not inspect untrusted ZIPs from unknown people.

A metadata-only archive inspection **cannot** confirm the content of `conversations.json` is valid, its CRC matches, the complete file is intact, the source is genuine, the user owns the account, or that Google imported the history. A malicious ZIP can carry benign central-directory metadata with corrupted payload; the inventory intentionally reports `full_zip_integrity_verified=false`. A filename hint is only a hint. No age/region/Google privacy consent is bypassed.

The report excludes account IDs, filenames, local paths, conversation titles, archived message text, attachments and hashes of those contents. It includes fixed booleans indicating `provider_origin_authenticated=false`, `archive_member_payloads_read=false`, `user_history_persisted=false`, `gemini_acceptance_verified=false`, `automatic_bidirectional_sync_verified=false`, `disk_writes=0` and `network_calls=0`. Only the summary remains in RAM until reset or guide closure.

## Evidence & verification

- `tests/test_native_export_inventory.py`: uses actual synthetic ZIP32 archives to prove member payload methods are NEVER invoked, the output never contains sensitive sentinel strings or ZIP filenames/paths, files are not altered, ChatGPT common/numbered JSON basename hints are recognized without reading JSON, Claude structure remains unverified, and archive corruption, ZIP64 sentinel, encrypted header, Zip Slip traversal, symlink, duplicate, oversize, extreme compression ratio and fake content-integrity cases fail closed.
- `tests/test_native_export_inventory_tk.py`: hosted Windows actual Tk UI tests with mocked owner decisions and file picker. They prove no picker/read without initial approval, no read after denied second review, valid synthetic ZIP inventory only after both reviews, no browser/HTTP operations, no displayed path/private content, summary discarded on reset, and source change mid-dialog refuses the read. Hosted scripted buttons are NOT physical owner clicks.
- `.github/workflows/memory-checks.yml`: new cross-platform ZIP safety gate plus hosted Windows Tk dual-consent gate; full regression and actual Windows frozen-EXE smoke, package inventory and artifact publication must pass on final exact feature-branch HEAD.
- No physical owner PC, real official export file, actual Gemini account or consumer app history has been accessed/tested in this assistant session.

## Official sources (as of 2026-11-05)

- OpenAI: [Exporting your ChatGPT history and data](https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data).
- OpenAI: [Transfer exported conversations between ChatGPT accounts](https://help.openai.com/en/articles/9106926-transfer-exported-conversations-between-chatgpt-accounts). Documents `conversations.json` and numbered conversation JSON files for larger exports; transferring JSON as reference does not restore native sidebar chats.
- Anthropic: [Export your Claude data](https://support.claude.com/en/articles/9450526-export-your-claude-data). It documents data exports but does NOT define an evergreen ZIP member-name schema verified by VARYN.
- Google: [Import from other AI platforms to Gemini Apps](https://support.google.com/gemini/answer/16868299?hl=en). Native user-driven import eligibility and privacy restrictions remain separate from this optional local ZIP envelope check.

## Next product gates

Physical owner acceptance of the portable app and user-chosen export, real memory footprint and malware/AV compatibility on the Windows laptop remain unobserved. To build an opt-in, encrypted, reliable local knowledge index from actual exported conversation content would require a separate design and owner approval, privacy/retention policy, content-level safety controls and substantial performance testing before enabling private data parsing. It is NOT silently turned on by this stage.

The seven requirements under `varyn.option_c_gate` remain BLOCKED: provider-sanctioned authenticated consumer-app history **read and write** interfaces, scopes, change detection and version IDs, deletions/retries, privacy and end-to-end true bidirectional verification are not provided by local ZIP inventory or one-time Gemini import. Preserve PR #1 as DRAFT; do not change `main`.
