# VARYN 17S-1 | Reviewed synthetic file tool gateway

Date: 2026-11-04. This is the **first bounded slice** of 17S, not full completion.

## Implemented

- varyn/tool_gateway.py connects an existing host-created, time/operation-limited ScopedFileGrants capability to an actual local read of a VARYN-generated SyntheticFixture text file.
- An exact proposal (tool, one built-in sample filename) is reviewed through a separate Tkinter yes/no dialog showing the intended read and SHA-256 digest before execution.
- Denied proposals perform no reads; approvals are single-use; tampered digests, revoked/expired grants, failed reads, and replay fail closed. Every read consumes an existing grant operation.
- Even after approval, the resulting file contents must equal VARYN's fixed synthetic sample. Files replaced or edited with any other bytes are not returned.
- The approved result is displayed only in the desktop RAM transcript. It is never automatically sent to any AI model, provider API or external tool.
- Untrusted model tool intent and 17O JSON task plans cannot invoke this gateway; no generic filesystem, shell, network, external application integration or writes are enabled.
- tests/test_tool_gateway.py contains permission, revocation, expiration, privacy, integrity, replay, limit, invalid tool and headless desktop callback tests; a dedicated GitHub Actions step runs on Windows and Ubuntu.

## Explicit limitations

This is a genuine **local read of a temporary file created by VARYN**, not access to arbitrary personal files. UI approval remains a trusted Python callback assertion, not authenticated proof that the Windows account owner personally consented. The existing scoped reader is not a full OS security sandbox and the gateway exposes no native model tool registration. The tool transcript stays in RAM and is never included in model context by this feature. No real-world autonomous agent task, financial operation, external API request or personal-data processing is authorized.

## Verification gate

Mark 17S-1 verified only after the **final documentation/code commit** finishes Windows/Ubuntu CI and the exact head SHA is confirmed. Physical-owner GUI testing on the target Windows device is a separate acceptance gate; the hosted Windows Tk button tests do not prove human interaction. Keep PR #1 draft and main unchanged.

Next: 17S-2 threat model for trusted user identity and app-scoped authorization, controlled safe tool extension, robust provenance, prompt-injection containment, end-to-end acceptance. Official consumer ChatGPT/Claude/Gemini app-history bidirectional synchronization remains externally blocked and is not replaced by an API aggregator.


## Regression extensions

The first Windows test failure was caused by platform-default CRLF translation in the generated fixture, while the tool gateway deliberately required the exact stored sample. The fixture writer now emits identical UTF-8 LF bytes on Windows and Ubuntu, verified by a raw-byte test; **the integrity comparison remains strict**. The in-memory tool audit is now bounded to 64 events, including after repeated abandoned proposals. An additional hosted Windows Tk test invokes the actual grant, review, deny, approve and revoke buttons using mock decisions and verifies zero model API requests. It does not prove physical human clicks or owner-device acceptance.
