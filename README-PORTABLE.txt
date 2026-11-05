VARYN-Portable | EXPERIMENTAL Windows x64 build
=================================================

This is an unsigned, non-production, single-folder Windows desktop build.
It includes the Python runtime. Python does NOT need to be installed on the PC.

WHAT TO OPEN
1. Download the artifact named varyn-windows-portable (NOT the source ZIP).
2. Extract the entire archive into a normal-user folder you control.
3. Keep VARYN-Portable.exe and the _internal directory together.
4. Run VARYN-Portable.exe as a NORMAL Windows user, NOT Administrator.
5. The manual official-app relay workbench opens automatically.
   Use harmless SYNTHETIC: data only.

IMPORTANT SECURITY AND PRIVACY BOUNDARIES
- The code is unsigned. This is NOT a Microsoft-certified release.
- Do NOT turn off Microsoft Defender, SmartScreen or antivirus to force-run it.
  If Windows blocks it, stop and use the reviewed source-only ZIP instead.
- No automatic sync with official ChatGPT, Claude or Gemini consumer app
  histories/memories. No account cookie extraction or login capture.
- Model API calls are disabled by the portable entrypoint. Other features in
  the existing desktop may request separately approved public network access;
  don't enable them during the offline pilot.
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
