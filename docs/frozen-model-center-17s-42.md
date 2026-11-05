# VARYN 17S-42 | ACTUAL Frozen Windows EXE Model Center Acceptance

Date: **2026-11-06 WIB**. This milestone closes an important verification gap between source-level Python tests and the Windows **PyInstaller-frozen one-folder VARYN-Portable.exe**.

## Fixed model-center run inside the actual frozen EXE

The existing, previously shipped **`--smoke-only`** route now calls `varyn.frozen_model_center_smoke.synthetic_center_acceptance(window)` after constructing the real native Tk windows and before destruction. This is **NOT** a new generic test CLI or a new provider permission; the existing smoke-only entry remains offline with `DesktopController(allow_live_providers=False)`, `allow_universal_model_network=False` and zero provider secrets. Only fixed synthetic UI settings are used.

The fixed test exercises a real Tk `ModelControlCenter` within the frozen process:

1. Verify that the center starts with no registered prices, no request underway, receipt disabled, no network/upstream authorization and an untouched in-memory request budget.
2. Attempt to add a `fake/fake-test` offer *without* quote/route review; verify it is rejected.
3. Explicitly mark a **fictional zero-price** fake offer owner-reviewed **only inside the CI fixture**, register it, exercise price preview and offline readiness, with zero network requests and no quota use.
4. Deny the exact fixed `SYNTHETIC:` fake request by replacing the review callback *only during this test fixture*. Verify denied review creates no budget reservation, answer or external model request.
5. Return one **CI-simulated approval for the fixed fake request only**. Verify the exact static content and expected heading were reviewed; pump actual Tk events until worker's simulated fake reply appears. Verify exactly one in-memory reservation, no provider receipt, no network enabled, no upstream approval, and legacy provider controller still zero requests.
6. Clear the RAM registry; add a **fictional** `deepseek/synthetic-no-provider-call` offer, set the GUI network checkbox ON while the **desktop-level live capability remains OFF**, and verify the send is rejected **before review**. No key access or network.
7. Close the real model-center window and confirm its offers are discarded.

**Important authority boundary:** The CI fixture's pretend approval is **not** a real person's consent and never authorizes a network request. The fixed fake provider has no external endpoint. Real provider credentials, a signed-in consumer account, a real local 9Router service, or any actual remote API are never contacted.

No extra process mode was introduced: `VARYN-Portable.exe --smoke-only` is already a no-action, offline test entry. Do **not** run `--smoke-only` for normal work; launch the EXE without arguments as a normal Windows user.

## Test and packaging gates

- `varyn/frozen_model_center_smoke.py`: the no-network fixed synthetic GUI acceptance. Fail closed if the real legacy model controller or independent gateway capability is live-enabled. No user-supplied task, URL, key or file path.
- `varyn/portable_entry.py`: invokes this acceptance on real frozen Tk, closes in `finally` after running it. Preserves normal user-launch behavior.
- `tests/test_frozen_model_center_smoke.py`: cross-platform rejection of missing/live owner and Windows hosted native Tk positive exercise with external network post mocked to raise if accidentally called. The same fixed suite is an explicit `memory-checks.yml` CI step; Windows package job runs the actual unsigned frozen EXE smoke.
- `tests/test_portable_windows_release.py`: previous mock-based portable entry smoke contract now requires the new entry to invoke the acceptance; does not pretend MagicMock is a real Tk widget.
- Baseline historical frozen four-process Windows DPAPI file write/read/overwrite/tamper tests remain in the packaging job. They test *separate historical synthetic draft storage*, not the 17S-42 GUI request or actual model calls.
- Exact-HEAD Windows, Ubuntu and frozen packaging jobs must all be **SUCCESS** before 17S-42 is deemed CI-green. Publish the run, discovered test counts, artifact IDs, hashes and expiry in the permanent PR #1 audit.

## Still NOT verified

- No actual provider API key, real HTTPS request, genuine 9Router upstream, real quota or provider billing authentication was used. Real account live smoke and the owner's Windows laptop acceptance require **direct interaction by the owner**, not simulated remote screenshots or API tokens in chat. An estimate is not a guaranteed money cap; routers may internally switch providers. The unsigned portable executable has not passed the owner's device compatibility and code-signing/SmartScreen acceptance.
- Strict preservation of Option **B**: multi-model APIs and owner-reviewed manual app handoffs are extra capabilities. Original Option **C** consumer ChatGPT/Claude/Gemini **automatic native two-way account history/memory sync remains BLOCKED**, separate from API completions.
- The test is a **single frozen process** with real GUI and a fake responder. It does not prove end-to-end authenticated external model execution or frozen EXE real-provider receipt persistence, nor a separate-process historical archive-to-fresh-task workflow.

No `main` changes or PR merge. PR #1 stays **OPEN/DRAFT**.
