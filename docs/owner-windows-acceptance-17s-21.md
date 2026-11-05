# VARYN 17S-21 | Owner Windows acceptance readiness and minimum-screen consent reachability

Date: 2026-11-05. Stage: **implementation committed; exact final HEAD CI and physical owner-device acceptance must be checked separately**. No personal data, real provider history or new capability enabled.

## Specific product defect addressed

The existing 17S-20 consent dialog was correctly implemented but its entry button was positioned after many vertically packed widgets in a fixed 760x650 Tk window with no page scroll. On a 540x480 supported minimum window, later controls could be inaccessible. Passing a programmatic `Button.invoke()` did not demonstrate an actual owner could reach the button.

## Implementation

- `varyn/desktop.py` wraps the existing, otherwise unchanged tool controls in a Tk `Canvas` with a persistent `ttk.Scrollbar`. The scroll region updates with content height, and the embedded frame follows the viewport width. Mouse wheel scroll works on the page, but does not take wheel input from the existing chat transcript and prompt `Text` widgets. No external modules or network requests are introduced.
- All existing desktop actions, including the explicit 17S-20 parent-only synthetic count review, remain accessible by scrolling. This is a UI reachability improvement, **not** a new permission or proof of OS confinement.
- `tests/test_desktop_scroll_tk.py` uses an actual hosted Windows Tk window at 540x480, finds the existing 17S-20 button in the widget tree, scrolls it into the viewport, invokes a mocked rejection, and verifies the transcript and no AI provider request. It also checks wheel behavior, transcript scroll isolation, and close behavior. Automated input is not a human gesture.
- `varyn/owner_acceptance.py` extends the pre-existing local owner self-report checklist with two mandatory 17S-20 observations: explicit **No** must not read the source and must not display a sum; explicit **Yes** must display the parent-local synthetic sum 21 without provider request. `tests/test_owner_acceptance.py` insists that skipped/failed steps prevent a success label, validates fixed answers, and never accepts free-form private text.
- `.github/workflows/memory-checks.yml` adds an early mandatory hosted Windows viewport test and a cross-platform owner-report contract test.

## How to run manually on the owner's Windows device

Use a **normal, non-administrator PowerShell** in the already cloned VARYN repository and an ordinary signed-in desktop session. Do not enter private documents, customer data, tokens or paid API credentials.

```powershell
git fetch origin
git switch feat/local-memory-prototype-20261103
git pull --ff-only origin feat/local-memory-prototype-20261103
py -3 -m unittest discover -s tests -p "test_desktop_scroll_tk.py" -v
py -3 -m varyn.owner_acceptance --synthetic-only --interactive
```

The owner acceptance command asks for fixed yes/no/skip observations. It instructs opening a second terminal with `py -3 -m varyn.desktop`. Use provider `fake`, keep network consent off, scroll to the 17S-20 button, select **No** once and **Yes** on a fresh preview. A valid owner report requires all eight checks to be reported positively **and** the synthetic CLI test to pass; if any step is skipped or fails, the result is incomplete. It is a **self-report**, not authenticated telemetry or independently verified physical mouse clicks. The report is printed to the terminal and not uploaded or stored by this tool.

Do not automatically overwrite a dirty local branch. Back up local edits and inspect `git status` before switching if needed. The test does not require admin privileges or a new database path.

## CI truthfulness and future gate

- Baseline 17S-20 code was green at [Actions #41979274474](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41979274474), 821 tests per OS.
- Initial scroll-only [Actions #41981959478](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41981959478) encountered a Windows Tk interpreter/variable finalization failure during the full suite (after the UI change); do not mark stage 17S-21 green based on Ubuntu only. Further commits/runs must distinguish deterministic failure from intermittent threaded Tk cleanup.
- A final HEAD Windows+Ubuntu SUCCESS proves tested code behavior on GitHub-hosted runners, **not** physical owner-PC acceptance. The latter must be user-executed.
- `main` must remain unchanged and PR #1 must remain draft. No general file-grant, live provider, official-app bidirectional sync, or production AppContainer access is authorized. `ProcessRepoFetcher.status()['os_sandbox']` remains false.

## Decision before next milestone

Do not promote VARYN to user-private document handling before local owner acceptance and a security review of reparse-point/handle races, UI reentrancy, ability to revoke, and how the trusted host authenticates owner approval. Consumer-app ChatGPT/Claude/Gemini two-way synchronization (**Option C**) remains unimplemented independently of this UX stage.
