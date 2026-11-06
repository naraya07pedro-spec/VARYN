VARYN-Portable | EXPERIMENTAL Windows x64 build
=================================================

This is an unsigned, non-production, single-folder Windows desktop build.
It includes the Python runtime. Python does NOT need to be installed on the PC.

WHAT TO OPEN
1. Open https://github.com/naraya07pedro-spec/VARYN/releases
2. Download the latest successfully published unsigned Windows x64 ZIP.
3. Verify the ZIP SHA256 against that exact release's digest.
4. Extract the whole archive into a normal-user folder. Keep the EXE,
   _internal runtime, manifest and owner PowerShell launcher together.
5. Run the launcher as a NORMAL Windows user, NOT Administrator.
6. VARYN opens to the new calm, nontechnical Home screen (no robot imagery).
   English is the default, with Indonesian, Spanish and French available
   from the visible language dropdown and Settings. Language preference is
   saved locally, without credentials or chat content.
   The main window can be maximized, restored and resized (native Windows
   titlebar or the in-app Maximize/Restore button); it opens maximized on
   Windows. Home provides real chat, task tracking and an honest directory of
   yet-to-be-connected apps. History is RAM-only for this app session.
   Type a message in the chat and click Send.
   Offline demo never returns an actual AI-generated answer.
   For real AI answers, select AI settings and: choose OpenRouter/DeepSeek,
   paste your provider API key, press Load models, search and select a model,
   review its published prices, then press Use selected model. The key remains
   in this app process RAM only and is not written to disk/env or GitHub.
   Provider /models returns available IDs but cannot guarantee actual credit
   balance; prices are snapshots, NOT hard provider billing caps.
   Each real prompt still needs ONE network consent and exact text approval.
   The obsolete technical Tk root window no longer appears behind the home.
   Tasks save in unencrypted user-local SQLite and update DUE status while
   the app is running, but DO NOT automatically execute.
   Connector, plugin and skill entries are NOT authenticated connections.

MEMORY AND TELEGRAM (ALPHA 7 EXPERIMENTAL)
- Memory page: manually select an official ChatGPT export ZIP (or
  conversations.json), select conversations, and confirm import. Selected
  plain-text excerpts are encrypted with Windows DPAPI at rest to the same
  user account. The importer does NOT auto-upload or sync accounts.
- Search saved memory, choose a result and Insert into Chat; or explicitly
  check Use saved memory before one question. The full expanded prompt is
  visible to the owner and requires the existing provider approval.
- Apps page: Telegram bot can be started by the owner with their PRIVATE
  BotFather token and numeric Telegram ID. Token stays in RAM. Set an actual
  OpenRouter or DeepSeek model and provider key in the app first.
- Authorized Telegram DMs use /ask <text>, then /confirm CODE within
  two minutes to approve one provider request (charges may apply).
  VARYN ignores unauthorized senders, bot messages and group chats.
- Telegram polling works ONLY while VARYN is open and the PC is running.
  No 24/7 uptime, voice/media support, chat sync or scheduled delivery.
- WhatsApp is NOT YET CONNECTED. Do not assume Telegram setup gives access
  to WhatsApp or other third-party accounts.

IMPORTANT SECURITY AND PRIVACY BOUNDARIES
- The code is unsigned. This is NOT a Microsoft-certified release.
- Do NOT turn off Microsoft Defender, SmartScreen or antivirus to force-run it.
  If Windows blocks it, stop and use the reviewed source-only ZIP instead.
- No automatic sync with official ChatGPT, Claude or Gemini consumer app
  histories/memories. No account cookie extraction or login capture.
- LEGACY provider calls remain offline in the portable entrypoint. The
  separate Universal Model Gateway is live-CAPABLE in normal user launch,
  but every model GET or chat request still requires explicit owner review,
  independent network permission and your OWN OS environment API credential.
  No such model request is made automatically. Other older features may also
  have separate public network approvals; leave them OFF during offline tests.
- Opening a provider homepage and clipboard copying require separate user
  approval. The provider/browser runs independently from VARYN.
- This is NOT a production OS sandbox or confidential encrypted storage.
  Do not use real customer data, private conversations, files or credentials.
- The app is a portable folder, NOT a signed installer or Windows service.
- Temporary RAM and OS clipboard behavior remain subject to the existing
  explicit approvals and limitations.

BASIC CHECKSUM
The accompanying BUNDLE-SHA256.json records the individual file hashes.
For example, from a normal PowerShell in the extracted folder:

  $expected = (Get-Content .\BUNDLE-SHA256.json -Raw | ConvertFrom-Json).main_executable_sha256
  $actual = (Get-FileHash .\VARYN-Portable.exe -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expected) { throw 'VARYN portable EXE changed' }

IMPORTANT: An attacker could change both an unsigned EXE and its adjacent JSON.
The self-published JSON is an integrity check, NOT a developer signature or
independent trust attestation. Compare with the exact GitHub Actions run and
repository commit before trusting the build.

Source code and full provenance:
https://github.com/naraya07pedro-spec/VARYN/pull/1

OWNER ACCEPTANCE IN THE APP (17S-32)
- In the workbench, select "17S-32 | Owner PC acceptance checklist".
- Run its manual steps with harmless SYNTHETIC: inputs in official apps.
- Mark each item pass/fail/not_checked, then Review fixed self-report.
- Copy is optional and requires a SECOND explicit approval. No auto-upload.
- This is an owner SELF-REPORT, NOT audited browser delivery/human identity.
- Closing discards the report in RAM; approved Windows clipboard copy can persist.
- No private ZIP, real conversations, tokens, or passwords for this test.

17S-33 | OPTIONAL ENCRYPTED SYNTHETIC DRAFT CONTINUITY
- In the workbench, choose Save encrypted synthetic draft. Review exactly,
  choose a NEW .varyn file; existing files are never overwritten.
- Later on the SAME Windows user profile, choose Restore encrypted draft,
  select that .varyn file and review the exact contents before applying.
- Only current synthetic task/note, project/topic and destination are saved.
- NO pasted provider reply, approval token, clipboard content, history,
  memory board, relay hop state or app connection is persisted or restored.
- DPAPI is tied to Windows user/profile; this is NOT cross-device portable,
  ransomware-proof, a complete backup or a production secret vault.
- Save is never automatic. No API calls or native provider sync are made.

17S-34 | FROZEN PROCESS RESTART VERIFICATION (HOSTED WINDOWS CI)
- The matching GitHub Actions run now starts the actual unsigned portable EXE
  four separate times against one temporary SYNTHETIC DPAPI fixture:
  encrypt NEW -> restore in NEW process -> refuse overwrite -> refuse tamper.
- This is an automated test on a GitHub-hosted Windows runner, NOT on your PC.
- It is not browser account verification, approved consumer-app history import,
  or native two-way ChatGPT/Claude/Gemini memory synchronization.
- The owner should still test Save -> fully exit -> reopen -> Restore on their
  own device, under their normal Windows user account. Do not disable AV.

17S-35 | GUIDED MANUAL 3-APP WORKFLOW (NO CONSUMER SYNC)
- In the focused workbench, type a harmless SYNTHETIC: fictional task.
- Click "17S-35 | Start three-app guided review". Stage 1 is ChatGPT.
- For each stage, separately approve opening the pinned official website,
  review/copy the exact packet, paste it YOURSELF, and paste the reply back.
- Review the EXACT pasted reply and accept it locally. Then click
  "17S-35 | Prepare next app after reviewed reply". VARYN selects Claude,
  then Gemini and writes a stage-appropriate synthetic draft task.
- Neither site opening, clipboard copy, nor provider delivery is automatic.
- Claude is asked to summarize the first draft so Gemini can use that summary.
  Gemini receives the last reviewed reply, NOT all account histories.
- All three stage flags are transient RAM only; no native app history sync.
- "Discard guided flow and relay RAM" revokes this local temporary state.

17S-36 | FULL GUIDED REPLY RECORD IN RAM, BOUNDED NEXT-APP EXCERPTS
- The guided flow keeps all three exactly reviewed synthetic pasted replies
  in RAM with local return digests and unverified claimed source names.
- "17S-36 | View complete locally reviewed replies (RAM)" shows full replies.
- Claude/Gemini handoff packets use separately labeled up-to-540-character
  excerpts of prior replies; Gemini includes both ChatGPT and Claude.
  TRUNCATED notices show when original content is not fully transferred.
- All copies still require fresh EXACT packet review and owner approval.
- No native provider account sync, auto-export, disk save or background read.
- Discard/close clears full RAM ledger, but cannot retract OS clipboard data.

17S-37 | SAVE COMPLETED THREE-AI SYNTHETIC SESSION ENCRYPTED, OPEN READ-ONLY
- Finish all three guided ChatGPT -> Claude -> Gemini synthetic handoffs.
- Choose "17S-37 | Save completed 3-AI encrypted archive"; inspect ALL text,
  approve, and select a NEW .varyn-archive file. No existing file overwritten.
- On a later session in the SAME Windows profile, select
  "17S-37 | Open saved 3-AI archive read-only". Review full contents first.
- Loaded archives are READ-ONLY, not active relays. Previous consent, hops,
  clipboard permissions and model/consumer-app history are NOT restored.
- Only test with fictional SYNTHETIC data; DPAPI is not cross-device backup.

17S-38 | RESUME FROM ENCRYPTED THREE-AI ARCHIVE AS FRESH MANUAL TASK
- In a NEW idle relay, pick an original archived stage 1 ChatGPT, stage 2
  Claude or stage 3 Gemini. Click Select encrypted archive excerpt (review).
- Choose a .varyn-archive created from a completed SYNTHETIC three-stage
  session, review its EXACT bounded unverified excerpt, then approve staging.
- A NEW harmless synthetic continuation task appears in the editable task
  field. The archive is NEVER imported as an active or approved relay.
- The Include reviewed old excerpt checkbox starts OFF. Check it yourself
  to include the excerpt on the next NEW manual packet. Approve the final
  exact clipboard packet separately, then paste into the official app.
- Wrong stage, active prior relay, stale selection, denied review and
  unsupported/corrupt archive are refused. Discard/close clears local
  excerpt state, but OS clipboard content cannot be retracted.
- The archived source label is only a USER claim, not authenticated app
  history. Excerpts are capped at 480 characters and may be truncated.
- No automatic model request, native app read/write, history sync, or
  restoration of earlier session consent, browser state or credentials.

17S-46 | ASK A REAL AI MODEL (OWNER-TYPED TEXT ONLY)
- Open "17S-40 | Open Model Control Center (owner opt-in)" in the main app.
- Choose a model (OpenRouter, DeepSeek, or permitted 9Router), review exact
  input/output prices, and add your offer. The default FAKE model never calls
  an external provider.
- Replace the SYNTHETIC: sample in the task field with your own question.
  Check "Authorize MY typed non-synthetic text for ONE reviewed request".
- Set a conservative estimated-token ceiling and enable one network request.
  Read the complete exact outgoing request and approve it separately.
- With a real API key loaded by Start-VARYN-OwnerPilot.ps1, VARYN can now
  send that SINGLE typed task and display the model response in RAM.
- The real-task toggle resets OFF after an approved request. No automatic
  conversation history, file access, tool execution, retries or fallback.
- Never paste sensitive customer data or credentials. The provider can retain
  your transmitted prompt. Local cost estimate is not a billing hard cap.
- This is NOT native ChatGPT/Claude/Gemini consumer account synchronization.

17S-39 | UNIVERSAL MODEL REGISTRY + PINNED CHEAP/FREE MODEL GATEWAY
- New code: varyn/model_registry.py (dated, owner-reviewed price offers);
  varyn/gateway_chat.py (pinned OpenRouter, DeepSeek, local 9Router);
  varyn/universal_gateway.py (explicit opt-in and in-process budget).
- TEST WITHOUT AN API KEY: python -m varyn.model_registry
  Prints only a fictional model-choice summary; no network request.
- All live model API calls are DISABLED by default. Programmatic use needs
  allow_network=True, a fresh approve_request=True per call, and the
  correct environment key: OPENROUTER_API_KEY, DEEPSEEK_API_KEY,
  or VARYN_9ROUTER_API_KEY. Never put keys in chat, repo or log.
- 9Router's local gateway is PINNED to 127.0.0.1:20128, not public.
  It also needs authorized_upstream=True. Its OWN fallback may change
  which provider/model bills, even if VARYN does not auto-fallback.
- Original pilot API defaults to SYNTHETIC: tasks. 17S-46 supports real
  owner-typed tasks only with an additional explicit opt-in per request.
  A 'free' or 'cheap' claim requires fresh explicit owner-reviewed
  input AND output prices; unknown/stale prices refuse auto-selection.
  Inferred token and cost estimates do not enforce real billing caps.
- This stage exposes a Python gateway, NOT a finished model-chooser GUI
  or verified live provider connection. Portable EXE startup and previous
  DPAPI regressions do NOT independently prove live model routing.
- ChatGPT/Claude/Gemini official consumer-app account history and memory
  are NOT synchronized by this gateway. Option C remains BLOCKED.

17S-40 | MODEL CONTROL CENTER REAL WINDOWS GUI (OPT-IN, NOT NATIVE APP SYNC)
- Main VARYN Tk: "17S-40 | Open Model Control Center (owner opt-in)".
- Add a provider/model plus your OWN verified USD per 1 million input/output
  tokens, price date and two separately checked quote/route confirmations.
  This is RAM only; do not assume VARYN verified real pricing or free quotas.
- Route Auto picks the lowest owner-quoted eligible estimate, OR explicitly
  select an exact registered model. Price age >30 days is refused.
- Preview: NO network. For a real model, choose one bounded fictional
  SYNTHETIC: task, enter estimated input/output token limits and estimated
  USD ceiling, check network ON, and separately authorize 9Router upstream.
- The EXACT approved request is shown in a scrollable modal. Only a fresh
  affirmative owner decision may dispatch ONE request. No auto-retry.
- API key is read only from your operating-system environment when dispatched:
  OPENROUTER_API_KEY, DEEPSEEK_API_KEY, VARYN_9ROUTER_API_KEY.
  NEVER paste secrets into GUI task, chat logs or source code.
- 9Router endpoint stays http://127.0.0.1:20128; upstream account behavior
  and provider fallback are NOT attested. No consumer login/cookie scraping.
- The old Portable provider controller stays OFFLINE; the new Model Control
  Center separately permits owner-consented live requests only in NORMAL
  user-launched mode. --smoke-only NEVER permits live network.
- GUI uses a dedicated thread for request execution, not for Tk updates.
  Closing after dispatch cannot cancel an in-flight provider charge.
- The preview budget is only an ESTIMATE, not guaranteed provider billing;
  RAM request count limits reset after the application restarts.
- Neither developer tests nor the EXE smoke verify real external API delivery.
  Native app ChatGPT/Claude/Gemini two-way memory sync (Option C) remains BLOCKED.

17S-41 | CHECK MODEL API READINESS LOCALLY AND SAVE METADATA-ONLY EVIDENCE
- In Model Control Center choose and register an explicitly dated/reviewed
  model quote. Press "17S-41 | Check readiness (NO network)".
- VARYN only checks if the correct OS environment variable is nonempty,
  whether the current window's one-shot network permission is ON, and
  whether local 9Router upstream authorization was explicitly granted.
  This check NEVER sends requests and NEVER displays the actual API key.
  READY means "eligible to ATTEMPT", NOT account/provider verified.
- Only a real owner-confirmed SYNTHETIC: test task may initiate a model
  request. Actual charges, quotas and model availability are NOT guaranteed.
  Both 9Router and OpenRouter may independently use provider routing/fallback.
- The model returned in the response's own metadata may differ from the
  selected model. VARYN shows an UNVERIFIED label and mismatch warning.
- Once a non-FAKE API response is locally parsed without a test transport,
  choose "17S-41 | Review & save content-free receipt". Explicit review and
  NEW JSON filename are required. It refuses overwrites. Only local time,
  selected/claimed model names, reported usage, estimated cost, and explicit
  NOT-VERIFIED status are written. NO prompt, answer, API key, or chat history.
  The receipt is not encrypted and is NOT signed proof of provider identity.
- No receipt is generated in FAKE mode. No acceptance receipt is auto-uploaded
  to GitHub, chat, or other providers. Owner manually keeps local receipt.
- CI exercises a real local TCP HTTP mock server for wire acceptance; that
  server is NOT actual 9Router or a remote AI account. No real provider key
  or payment is used by CI. Signed-in consumer memory sync stays BLOCKED.

17S-42 | REAL FROZEN EXE MODEL CENTER FIXED SYNTHETIC ACCEPTANCE
- Windows Portable build CI now uses the ACTUAL frozen VARYN-Portable.exe
  --smoke-only to run the real Model Control Center Tk widgets through:
  reject unreviewed fictional price, offline preview, missing-key-free FAKE
  readiness, denied owner-modal fixture, ONE CI-approved fake response,
  in-memory request counter, no real-provider receipt, refusal of a
  fictional DeepSeek request with the desktop live capability still OFF,
  and full RAM quote cleanup. NO external AI/9Router connection.
- Review approval is entirely CI-SIMULATED for a fixed harmless FAKE task,
  NOT a human approval and never permits a paid, remote, or actual API request.
- Use normal VARYN-Portable.exe (without --smoke-only) for interactive
  owner use; the user must still review and approve every live request.
- This smoke proves real frozen Tk fake-workflow wiring, NOT real model API,
  current free quotas, a signed executable, owner PC acceptance, or native
  ChatGPT/Claude/Gemini history/memory sync.

17S-43 | DISCOVER OFFICIAL API MODEL IDS BEFORE A LIVE PILOT
- Open main VARYN > 17S-40 Model Control Center > "17S-43 | Discover model
  IDs (official GET /models)". This is a NEW, separately reviewed network
  action, distinct from a billable inference request. There is NO automatic
  discovery, fallback, history import or hidden login.
- Choose OpenRouter, DeepSeek, or LOCAL 9Router. The network toggle is OFF
  by default; 9Router upstream authorization is also OFF. Store YOUR OWN key
  only in the current normal-user OS environment (never in chat or GitHub):
  OPENROUTER_API_KEY / DEEPSEEK_API_KEY / VARYN_9ROUTER_API_KEY.
- Tap "Review exact GET /models & request ONCE". Inspect endpoint/method
  and approve explicitly. List is capped to 60 safe model ID strings. An ID
  appearing does NOT prove the key works for inference, model availability,
  free usage, provider identity, or any price/quota/cost guarantee. OpenRouter
  GET /models can list public models without proving account entitlement.
- Select one ID and choose "Use selected ID". Both estimated price fields are
  BLANKED, quote review and route review flags reset OFF, and network/upstream
  permissions reset OFF. Manually verify actual prices/account status with
  the official provider before registering a quote or approving inference.
- Never use a fake 0 USD entry to bypass the need for price verification.
  VARYN cost estimation is NOT an actual hard spending cap. Real providers
  and routers can charge and switch providers even when a request fails.
- Frozen EXE --smoke-only tests only offline default and rejects catalogue
  access even if its local toggle is ON; it cannot validate your actual API.
- See docs/model-discovery-17s-43.md in repository for the full scope.


17S-44 | OWNER PC PILOT LAUNCHER INCLUDED AND SHA256-VERIFIED
- A NEW OPTIONAL Windows PowerShell script now ships inside the SAME portable
  folder: Start-VARYN-OwnerPilot.ps1. Keep it beside VARYN-Portable.exe,
  _internal, README-PORTABLE.txt, and BUNDLE-SHA256.json.
- Before opening ANY executable, compare the ORIGINAL downloaded whole ZIP
  SHA256 with the exact GitHub Actions artifact digest from PR #1. The local
  manifest is UNSIGNED and does not independently prove publisher identity.
- Open a NORMAL (not Administrator) Windows PowerShell in the EXTRACTED
  VARYN-Portable folder. Basic no-app, no-credential verification:
    powershell.exe -NoProfile -File .\Start-VARYN-OwnerPilot.ps1 -VerifyOnly
  Then normal OFFLINE pilot (no provider key inherited into child):
    powershell.exe -NoProfile -File .\Start-VARYN-OwnerPilot.ps1 -Provider offline
- OPTIONAL real-provider pilot, only with YOUR own legitimate provider API key:
    powershell.exe -NoProfile -File .\Start-VARYN-OwnerPilot.ps1 -Provider openrouter
  Or choose -Provider deepseek / -Provider 9router. The script verifies all
  bundled files first, then asks for key via HIDDEN PowerShell prompt.
  It does NOT print the key, place it on command line, or save it to disk.
  The process environment still contains the key in VARYN until VARYN exits;
  other sufficiently privileged local software may read that environment.
- Launcher clears common inherited provider/GitHub/AWS tokens in its own
  process before spawning VARYN, then sets only the selected provider key.
  It does not create permanent system environment variables or use setx.
  No provider network call occurs automatically after launching.
- The application still requires separate model GET or inference network
  toggle and exact owner review, even after credential setup.
  Provider pricing/free tiers/authorization and actual billing remain unknown
  until independently checked. Cost estimates are NOT hard billing caps.
- This launcher is UNSIGNED; if Windows PowerShell execution policy or
  Defender/SmartScreen blocks it, STOP. Do NOT bypass execution policy,
  elevate to Administrator or disable antivirus. For offline operation, the
  normal EXE can still be launched directly if Windows allows it.
- GitHub CI tests a REAL Windows PowerShell -VerifyOnly against clean
  synthetic bundle and deliberately tampered/missing/extraneous file cases,
  plus tests the script inside the real packaged one-folder EXE artifact.
  CI does NOT test your actual API credential, account, PC or provider bill.
- See docs/owner-pc-pilot-17s-44.md for full owner acceptance steps.


CONSUMER APPS HUB (ALPHA 8)
- Apps now shows logo-style local vector app markers and clickable controls.
  GitHub and Notion support real independent access-token probes via official
  HTTPS endpoints and an owner-triggered list of allowed resources.
  Their tokens stay in RAM. The app NEVER claims write access or OAuth scope
  inheritance from ChatGPT. Disconnect clears the token in this process.
- Telegram remains a real owner-approved Bot API connector (BotFather token,
  numeric owner Telegram user ID, local app must be running).
- WhatsApp and the remaining app/skill directory are NOT CONNECTED. Clicking
  a listed integration offers an official setup guide if one is known, or
  explains plainly that its adapter is not yet implemented. A clickable
  setup guide is NOT an authenticated connection.
