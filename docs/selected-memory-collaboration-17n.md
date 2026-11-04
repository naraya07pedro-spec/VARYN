# Checkpoint 17N: selected project memory -> three-stage collaboration

**Date:** 2026-11-04. Development branch: feat/local-memory-prototype-20261103. Draft PR #1. Main remains unchanged.

## Actual product capability

VARYN Desktop now accepts an **optional comma-separated list of 1 to 3 local note IDs** in the three-role collaboration dialog. It snapshots those exact records from the existing 17M opt-in SQLite database, bound to the currently selected project and configured local owner label. There is no automatic search, chat capture, prompt-derived retrieval, browsing of private files or model-selected memory. If even one requested ID is absent, deleted, or belongs to another project, the entire selection is rejected before any provider stage starts.

The snapshot uses the existing bounded `varyn.context.v1` adapter format and attaches source references (e.g. `memory:7`), project label, synthetic content, creation time and untrusted/source-unverified markers. It refuses notes that bypassed the 17M synthetic-only guard, duplicates, bad ID strings, and context packages over the existing API payload size cap.

The existing **Allow context sharing** checkbox is a required separate gate. A second, dedicated memory approval dialog shows the **exact selected note contents and source references** before any stage is queued. Declining this dialog stops the full plan without dispatch. For each live developer-model API stage, an additional stage-specific confirmation still names the model, possible charges, and onward information sharing. The warning explicitly states that the analyst gets the selected notes and later providers may see that information **indirectly** via the analyst/critic's generated outputs.

Only the **analyst** receives the structured memory context directly. The critic and synthesizer receive the original task and bounded, untrusted prior-model output, which can contain paraphrases or excerpts of the notes. Neither downstream stage directly fetches local memory. Engine results include `context_project` and `context_source_refs`; the Tk transcript displays source labels but does not automatically duplicate raw saved notes on completion.

## Strict limitations

- The underlying SQLite database is still **unencrypted** and only explicitly user-marked `SYNTHETIC:` development notes are accepted. A marker is not an actual privacy guarantee.
- The opt-in ID selection and approval prompts are **UI-level gates**, not authenticated owner identity and not an OS sandbox. Real sensitive personal notes are not approved for use.
- Context and source labels are untrusted; `source_verified=False` is accurate. The model may ignore source references or hallucinate citations. No factual verification or measured reasoning gains were delivered.
- The initial memory approval is for the **entire three-stage workflow**, with additional per-live-provider API approval. The user must understand that earlier outputs can leak the notes to later providers. Provider API billing is not capped in currency.
- The change does not read or write the **official consumer ChatGPT/Claude/Gemini conversation history**. Option C stays blocked pending evidence of supported read/write and authorization APIs. Developer-model endpoints are not a substitute.
- No automatic persistent agent checkpoints, automated model routing or production security hardening is included.

## How to test (synthetic only)

Start in a non-Administrator Windows session from a directory you deliberately selected:

```powershell
py -3 -m varyn.desktop --memory-db ".\\varyn-synthetic-notes.sqlite3"
```

Save an invented note such as `SYNTHETIC: alpha task reference` in project `VARYN` using **Save synthetic note**. Obtain its numeric ID from the local transcript. Type an invented task, enable **Allow context sharing**, click **Collaborate (3 roles)**, leave providers at **fake**, and type the numeric ID into **Selected memory IDs**. Click **Review and run 3 stages** and explicitly review the exact selected note. On acceptance the offline fake pipeline should complete with `MEMORY SOURCES` showing the chosen ID. Fake replies are placeholders and do not prove memory reasoning quality.

For external developer APIs, networking remains separately opt-in and may bill. Do not put personal or sensitive data into this unencrypted prototype.

## Tests and evidence

- `tests/test_memory_handoff.py` covers project isolation, ID parsing and missing IDs, note-injection refusal, explicit context approval, live provider warning content, provenance, first-stage-only structured context and no silent network work.
- `tests/test_memory_handoff_tk.py` is a Windows-hosted real Tk modal test (programmatically invoked, **not human clicks**) for exact ID entry, explicit preview and displayed source references.
- Both are included in CI alongside prior 17K–17M security, native Windows handle, agent and GUI regressions.
- Final passing CI SHA and test counts must be recorded in `docs/progress-log.md` once the full Windows/Ubuntu jobs finish successfully.
