# VARYN 17S-4 | Same-user public tool subprocess boundary

Date: 2026-11-04. This checkpoint strengthens the first permitted public GitHub metadata tool. **It does not claim OS sandboxing, biometric/password reauthentication or authenticated human presence.**

## Concrete change

Before 17S-4, a GitHub public metadata request ran in a background **thread within the desktop process**. It still shared the desktop process's environment and OS permissions. The new default desktop fetcher is `ProcessRepoFetcher`, which starts a dedicated short-lived **child Python process** for each already-reviewed public metadata GET.

- `varyn/public_tool_process.py` owns the child lifecycle. It launches the fixed absolute `varyn/public_tool_child.py` entrypoint using the trusted `sys.executable`, `-I -S`, `shell=False`, `close_fds=True`, and a minimal allowlisted environment. GitHub API tokens, provider keys, proxy settings, `PYTHONPATH` and user-site setup are **not inherited through environment variables**. Windows system runtime variables are allowed where necessary. The child executes under the **same OS account**, not a privileged isolation container.
- Only a strict `varyn.public_tool_intent.v1` JSON object enters the child's stdin. The parser independently rejects URL input and unregistered tools. Only one fixed public GitHub API endpoint is supported by `varyn/public_github_tool.py`.
- The child prints only bounded public metadata JSON on stdout. The parent caps the response at 4096 bytes and checks identity/format, then the existing gateway revalidates every approved field. Arbitrary GitHub descriptions, external instructions, system errors or tokens are not delivered to the model or UI.
- Each child has an eight-second supervisor timeout, while its HTTP client uses a five-second network timeout. A process failure consumes the existing one-use request budget; no automatic retry is attempted.
- The gateway's `revoke_active()` and `close()` invalidate its permission epoch **and** invoke the process fetcher's `cancel()` or `close()`. The fetcher attempts to kill its active child promptly. The parent rejects any late response. On Windows, the child is launched with `CREATE_NO_WINDOW` when supported.
- There is a single process at a time per fetcher and a single active request per desktop worker. GitHub network consent remains separate from AI-provider network consent and defaults OFF.

## What this does not guarantee

A Python child under the same OS user **is not a sandbox or a security principal**. It may retain the user's ordinary filesystem/network access if code is compromised. Python `-I -S`, environment minimization and handle noninheritance reduce accidental exposure but cannot stop malicious same-user code from opening personal files, impersonating consent, modifying the checkout, or using OS APIs. No restricted Windows token, AppContainer, ACL isolation, service broker, process signing, or authenticated desktop owner challenge is implemented.

Revoking a request may terminate a running child process, but cannot retract a network packet already sent to GitHub. Process termination is best-effort; Windows and Linux system behavior may vary. This tool does not access private repositories, write to GitHub, execute arbitrary shell commands, browse user-selected URLs, or create automatic model actions.

## Verification and acceptance

- `tests/test_public_tool_process.py` launches a **real child OS process** in the special offline self-test mode to verify isolated Python flags and no network. All actual metadata GET/kill/timeout scenarios use **fake process objects**; they do not contact GitHub.
- On Windows and Ubuntu CI, verify that the offline child launches, environment secrets and proxy variables are excluded, command/argv are fixed, invalid targets cannot spawn, revocation kills a fake blocked child, late results are dropped, concurrent execution is forbidden, timeout and malformed responses fail closed.
- All previous 17S-1/2/3 regressions remain in the suite. Verify on the exact final HEAD SHA after documentation updates.
- A real owner-laptop run, direct public GitHub HTTP endpoint acceptance, process RSS measurement on an ~8 GB Windows device, Windows user SID binding and actual OS-enforced sandbox/identity attestation remain **unverified**.
- The original **Option C** requirement of automatic two-way synchronization of official consumer ChatGPT, Claude and Gemini app histories is **still blocked by supported-interface feasibility**. This work does not silently replace it.

## Next high-value gate

17S-5 should focus on a genuine OS-enforced trust boundary (restricted token/AppContainer or separately provisioned broker with validated SID and ACLs), verify it on Windows, and keep private files/writes disabled until that boundary is demonstrably enforced. Do not invent security guarantees or real-network acceptance based on mocked tests.
