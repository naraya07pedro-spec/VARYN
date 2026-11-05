# VARYN 17S-25 | Human-reviewed project working context for manual official-app relay

Date: 2026-11-05. Experimental, **synthetic-only**, RAM-only. PR #1 remains OPEN/DRAFT against unchanged `main`. Final exact-head CI must be inspected; there is **no claim of physical owner-PC testing or automatic official consumer-app two-way synchronization**.

## Product problem

17S-24 bound one pasted reply to one outgoing request, but the next hop still copied an entire unverified AI answer. That is useful as source material, not necessarily reusable project context. Automatically adding unverified AI text to memory creates source confusion, poisoning and accidental cross-project disclosure.

17S-25 adds a **user-authored, explicitly reviewed working context board**. The owner must write an interpretation or next-step note, review its exact bytes and decide whether it is shared with the next official app. Nothing silently promotes ChatGPT/Claude/Gemini output into trusted facts or durable memory.

## Implemented

- `varyn/relay_working_context.py`: `WorkingContextBoard` with exact per-project+topic identity, limited to **eight** RAM notes across all projects and **three** notes in one project transfer. Text must be explicitly marked `SYNTHETIC:` and <=320 characters; projects and topic labels are strictly validated. No arbitrary filesystem reads, credentials, background provider requests or database writes.
- `propose` creates a fresh one-use, digest-bound, 90-second human review. `decide` accepts only that same still-pending review. A different text/classification/source reference for an existing exact topic is presented as a **conflict**, with the old text visible. Replacing it requires the dedicated `Replace existing project note` decision; duplicate inputs do not create another revision. Local revision increments on an explicit replacement.
- Note classification is `hypothesis`, `task`, or `owner_decision`. A label is the owner's classification, **not independent fact checking**. When a pasted reply was previously reviewed, its *local* outbound/return receipt can be bound as an unverified source reference, with a matching-receipt recheck after the UI modal closes. It does not authenticate a real provider.
- `WorkingContextSelection` includes only the notes for **one exact project**, with unique topic labels and `source_verified=False`. `OfficialManualRelay.prepare(..., reviewed_context=...) ` accepts only a valid selection; the packet quotes the owner note text as untrusted context with local revision and source label. Existing 3,600-character packet cap and exact packet/digest/TTL approval still apply.
- Desktop UI: an owner-editable topic field, **17S-25 | Review project working note (RAM-only)**, **17S-25 | Discard all temporary project notes**, and the checkbox **Include reviewed project RAM notes in NEXT official-app copy (opt-in)**. The checkbox is **OFF by default**. It does not share notes from another project or silently select missing notes. The owner sees the entire next outgoing packet and must approve its clipboard copy separately.
- `Discard` clears all working notes and disables the include toggle; desktop `_close` also resets the board. This does **not** recall previously copied clipboard text, remove remote app chat messages, cryptographically erase Python heap pages, or delete existing private provider history. The original `--memory-db` is **not** used or altered.

## Adversarial tests

- `tests/test_relay_working_context.py`: denial, one-shot replay, tampered preview, timeout, exact project isolation, duplicate, explicit conflict/replace, source-receipt mismatch, forged verified receipts, malformed topics, note limits, nonsharing default and exact next packet.
- `tests/test_official_manual_relay_desktop.py`: actual callback contract with mock modal/clipboard, first-app return -> owner note -> second-app copy, default no sharing, explicit sharing, wrong project blocked, conflicts and nested discard.
- `tests/test_relay_working_context_tk.py`: Windows-hosted real Tk widgets, mock human button approvals, clipboard containing only the reviewed selected project note and explicit reset. **Not a real human click or actual consumer app login**.
- `.github/workflows/memory-checks.yml` adds early required cross-platform checks plus a Windows-only native Tk test. Full Windows and Ubuntu unit suites must pass on the exact final documentation commit.

## Manual owner acceptance (not performed by CI)

From normal-user PowerShell on the PC, in a clean feature-branch checkout:

```powershell
git fetch origin
git switch feat/local-memory-prototype-20261103
git pull --ff-only origin feat/local-memory-prototype-20261103
py -3 -m varyn.desktop
```

Keep the VARYN model provider `fake` and its network/API consents OFF. Type `SYNTHETIC: Organize two next steps for my sample project.`, set project `VARYN` and topic `next_step`, then review/approve the 17S-25 temporary note. Change the same topic text and verify the modal visibly shows both versions with an explicit **Replace** option. Turn on the context include checkbox; type another synthetic prompt, choose official app and review the **full resulting packet** before copying. Confirm the packet includes only `VARYN` notes, with `untrusted` and `not verified` qualifiers. Turn the checkbox OFF and inspect a fresh outgoing packet, which must omit project notes. Finally use Discard and verify the board is empty and the checkbox OFF. Use actual official apps only with harmless test content and manual pasteback; do not enter any private documents, credentials, passwords or paid API keys.

This gives **controlled working continuity**, not secure permanent memory or official provider-side history sync.

## Remaining blockers

1. **Real owner-PC end-to-end acceptance** and usability at laptop screen sizes. GitHub-hosted Tk/button tests are programmatic and cannot attest a physical owner action.
2. **Official consumer-app history and memory read/write authority** for ChatGPT, Claude and Gemini. `varyn.option_c_gate` remains blocked. An official-app web homepage or model API is not a full authorized bidirectional history connector.
3. Durable, encrypted, scoped, owner-authenticated long-term memory suitable for non-synthetic content; safe conflict-resolution and revocation semantics. RAM board is deliberately discarded on restart.
4. A user-facing way to resolve/cancel individual working notes without clearing an entire board is a usability improvement, not a hidden permission escalation. Up to three notes can currently be shared per project.
