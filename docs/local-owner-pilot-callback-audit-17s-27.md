# VARYN 17S-27 | In-app local callback evidence, not self-report alone

Date: 2026-11-05. Stage: **experimental, in-memory callback audit only**. Commit and CI verification must be checked against the exact final HEAD. PR #1 remains DRAFT against unchanged `main`. No owner-PC observation, official app history access, account authentication, or automatic consumer-app sync has been demonstrated.

## User problem addressed

17S-26 shipped a usable one-click Windows source ZIP with a questionnaire, but answering `yes` did not prove any VARYN action actually reached its successful code path. The desktop could not show the difference between a user self-report and the in-process result of a consented copy or return review.

17S-27 exposes an **opt-in application callback audit** in the actual Tk desktop, not an API connector. This observes successful *local* operations, not a physical mouse click, an external browser paste, or the origin of a remote model response. A script or `Button.invoke()` can produce the same callbacks.

## Delivered capability

- `varyn/local_pilot_audit.py`: `PilotLocalAudit`, initially OFF. Owner explicitly starts a new in-memory session. At most **32** events are stored; an overflow is visible/refused instead of silently producing incomplete evidence.
- Only seven exact event codes are accepted: `homepage_launch_requested`, `approved_packet_copied`, `reviewed_reply_staged`, `working_note_reviewed`, `project_context_included_in_copy`, `relay_state_discarded`, `working_context_discarded`. Provider is strictly one of `chatgpt`, `claude`, `gemini` for the provider-specific codes. No arbitrary user input, URL, task, reply, clipboard bytes, local project name, account identity, timestamps, request IDs, digests, or credentials are accepted into audit records.
- Integration in `varyn/desktop.py` only **after successful callback paths**: browser launch request accepted by system browser function; reviewed OS clipboard packet written and acknowledged by the relay; user-pasted, outbound-bound reply staged; exact working note created/replaced; selected context actually included in an approved packet; explicit relay/working-context discard. Denied UI consent or failed/expired clipboard review does not produce a corresponding successful event.
- At top of Tk desktop: `17S-27 | Start local event audit`, `17S-27 | Review / copy audit`, `17S-27 | Reset audit`. A brief label shows active/inactive state and observed count.
- `Review / copy` shows an **exact read-only scrollable JSON report** and asks for another explicit clipboard-copy approval. It refuses to copy if the RAM report changed while the modal was open, and does not read the previous clipboard content. It may overwrite the system clipboard only after that new approval. JSON is not written to disk or uploaded by VARYN.
- The report's `local_two_target_attempt_observed` becomes true only when approved local clipboard copies target **two different official app identifiers** and at least one unverified reply was staged in RAM. The report always leaves `independent_human_click_verified`, `official_account_authenticated`, `remote_paste_or_delivery_verified`, `pasted_reply_provider_origin_verified`, `official_consumer_history_read_verified`, `official_consumer_history_write_verified`, `automatic_bidirectional_sync_verified`, and `production_private_access_authorized` as false. Even two local targets are NOT proof of reaching those websites.
- `Reset` requires owner review and clears the in-RAM audit. Desktop closure resets the audit too, without deleting browser history, third-party messages, or OS clipboard bytes. This report is neither digitally signed nor tamper-evident.

## Actual manual acceptance steps

1. Run the latest verified Windows source ZIP from its GitHub Actions artifact, or use the clean feature branch, as a normal Windows non-admin user. Double-click `Try-VARYN-Official-Apps.cmd` with Python 3.12+ and Tkinter installed.
2. Before beginning, click `17S-27 | Start local event audit` in VARYN. Keep VARYN API provider on `fake` and VARYN network/API consents OFF. Use harmless `SYNTHETIC:` prompts and notes only; never use passwords, real customer data or exported private chat histories.
3. Try browser launch and exact approved clipboard transfer to a FIRST official consumer app; manually paste it there. If the browser supports the account, manually copy a harmless reply back into VARYN and approve the return. Choose a SECOND app and approve a separate packet; review per-project working context as needed. These external steps are NOT automatically observed, and browser launch itself needs separate owner consent.
4. Click `17S-27 | Review / copy audit`, inspect all flags and the event counts, then approve copying **only the fixed status JSON**. Paste into a local text viewer or into the ChatGPT conversation if you choose; it has no transcript content or account IDs. Never assume this self-supplied JSON constitutes cryptographic or independent attestation.
5. Click `Reset audit` when done, then close the desktop. A later desktop session begins with auditing OFF.

You can still use the 17S-26 terminal questionnaire as a separate **owner self-report**. Its fixed answers and the in-app callback report answer different questions and must not be conflated.

## Tests and evidence boundary

- `tests/test_local_pilot_audit.py`: explicit activation, strict event/provider allowlist, no personal data, capacity, reset, false provenance and remote-sync flags.
- `tests/test_official_manual_relay_desktop.py`: denied vs successful browser/clipboard callbacks, local two-target flow, project-note opt-in, clipboard-review mutation and consented audit reset.
- `tests/test_local_pilot_audit_tk.py`: real hosted Windows Tk button tree and scripted events with mocked provider/browser actions. This is **not physical owner acceptance**.
- `.github/workflows/memory-checks.yml`: mandatory portable audit tests and Windows Tk early gate, followed by full suite. Do not call this stage CI-verified until **both OS jobs pass on the exact documentation/progress HEAD**.
- The previously approved source ZIP artifact has a seven-day retention period; each successful Windows CI run should publish an updated source ZIP. Neither Python scripts nor the audit grant private folders or production sandbox access.

## Remaining fundamental blockers

Actual end-to-end owner-PC testing remains **pending** until the user runs the artifact and supplies selected observations. The existing `varyn.option_c_gate` must remain blocked: there is still **no verified provider-sanctioned authenticated two-way read/write interface** for official ChatGPT, Claude and Gemini consumer conversation histories/memories. Provider APIs, manual clipboard transfers, simulated Tk clicks and this local callback audit do not satisfy Option C. Do not add browser-cookie scraping or infer authentication from OS browser launch.
