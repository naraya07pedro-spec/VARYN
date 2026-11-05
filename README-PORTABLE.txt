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
