# VARYN 17S-20 | Desktop owner review wired to bounded synthetic parent broker

Date: 2026-11-05. **Experimental local-only stage; exact-head Windows/Ubuntu CI pending at documentation commit.** No real personal documents, external provider, official-app sync, network, or production AppContainer child enabled. PR #1 must remain OPEN/DRAFT against unchanged `main`.

## Purpose

17S-18 proved that CI test code could simulate a trusted-parent owner decision before a bounded synthetic source reached a real hosted Windows AppContainer. That is not human consent. 17S-20 connects the same review/digest/one-shot source-validation contract to an **actual desktop Tk confirmation dialog**, without misrepresenting the local calculation as AppContainer sandbox execution.

## Implemented

- `SyntheticParentCountsFixture` generates a fresh disposable directory holding **only** a fixed `synthetic-parent-counts.json` payload, `{"counts":[4,6,11]}`. The action never accepts user-chosen paths, actual documents, model instructions, URLs or external file handles.
- `ParentSyntheticReadBroker(..., desktop_fixture=fixture)` is legal outside hosted CI **only** with an exact `SyntheticParentCountsFixture` object and matching generated path. Legacy arbitrary directory mode still requires explicit hosted CI opt-in. Desktop-only mode **refuses** `complete(raw_response)`: it cannot forge AppContainer evidence, and instead performs a trusted-parent in-process local completion with `os_sandbox=False`.
- `DesktopParentCountsAction` creates a disposable fixture and temporary SQLite `DurableOneShotJournal` and presents a **metadata-only preview** before content access. A one-use request ID/digest and 20-second TTL are checked before reading. Only approved, unexpired, source-stable requests are claimed before local processing; denial, forged digest, changed source, replay and closure must fail closed.
- The desktop button `17S-20 | Review parent-only synthetic count` shows the exact scope and digest in a Tk `messagebox.askyesno`. A rejection performs no source-content read. Approval returns **only total 21** from the VARYN-generated sample and states explicitly that there was no model, network, private file, or OS sandbox. A nested close or busy state must prevent execution.
- No encrypted long-term consent history is claimed: the SQLite journal is within the disposable temporary fixture and is deleted when the owner action closes. Its one-use durability applies only while that fixture/journal exists, not across a desktop restart.

## Tests and boundaries

- `tests/test_desktop_parent_counts.py`: generated source, owner decision, denial without read, wrong digest, changed source, TTL, no non-CI arbitrary roots, desktop rejection of fake sandbox response, one-shot claim, cleanup.
- `tests/test_desktop_parent_counts_ui.py`: host callback denial, approval, busy/closed/nested-close behavior using mocked dialogs.
- `tests/test_desktop_parent_counts_tk.py`: hosted Windows native Tk button is instantiated and invoked for deny and approve; automated `Button.invoke` with mocked `askyesno` does **not** prove a real human click or acceptance on the owner's PC.
- `.github/workflows/memory-checks.yml` runs dedicated 17S-20 tests early in Windows and Ubuntu jobs, then the full suite.
- Existing CI-only real AppContainer proof remains separately gated. **Do not** connect desktop to `windows_appcontainer_trial.py`, `ProcessRepoFetcher` private-file access, arbitrary file dialogs, or provider history. No production sandbox or general file authorization is established.

## 17S-19 Windows regression diagnosed during this stage

- The 17S-19 documentation HEAD `e777e1580532f3499a86e278c703d102d33d989f` had a **red Windows CI** ([run #41977234653](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41977234653)) although Ubuntu passed. The cause was not a passing isolated earlier run: Windows `os.lstat(path).st_ctime_ns` did not equal `os.fstat(fd).st_ctime_ns` for an otherwise valid sample.
- Metadata-field-only diagnostics in [run #41978400577](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41978400577) identified specifically `ctime`. `7f5136a93818f91ff0a0317c43c40ca19ffb650d` adjusts Windows comparisons to **path lstat vs path lstat** (including ctime) and **fd fstat vs fd fstat** (including ctime); stable device/inode/size/mtime/link-count remain cross-checked at open, and the parent path is rechecked after read. This is more precise than ignoring ctime entirely. No production-grade atomic whole-file snapshot is claimed.
- Final Windows+Ubuntu CI for the exact documentation HEAD is required. Do not report 17S-19 or 17S-20 green until the new run is completed and audited.

## Next acceptance gate

Actual owner-device Tk UI review, small-screen operability, cancellation and lifecycle tests, Windows file-handle security for a deliberately selected **non-sensitive** resource, and proof that no untrusted model input can invoke the trusted approval callback. Only then consider controlled personal document access. **Option C**, two-way sync with official consumer ChatGPT/Claude/Gemini applications, is independently unfulfilled.
