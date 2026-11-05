# VARYN 17S-30 | Provider-native one-time ChatGPT/Claude history migration into Gemini

Reviewed on 2026-11-05, based on provider Help Center instructions. This is **not** consumer-account API access, browser automation, a VARYN file importer, or Option C bidirectional synchronization. All actions on account data occur **directly in the providers' official sites** and require the owner's explicit action. Physical owner acceptance is PENDING.

## Why this is more than synthetic message relay

OpenAI documents exports of ChatGPT consumer chat history (including a ZIP). Anthropic documents exports of Claude personal chat history, with workspace eligibility distinctions. Google **officially documents importing full chat-history ZIP files from other AI platforms, including ChatGPT and Claude**, directly into eligible Gemini personal accounts. This supplies a real *one-time, human-driven account data migration direction* into Gemini, not merely copy/paste of a tiny fictional message.

This is different from complete Option C. VARYN still cannot access an existing consumer chat history through an authorized automated read/write endpoint, detect changes, update or delete native chats, or automatically maintain a three-way shared history. Gemini native import is not a reverse ChatGPT/Claude history writer, and importer success cannot be inferred from launching Gemini's homepage.

## Exact supported direction and user prerequisites

- **ChatGPT -> Gemini (manual one-time)**: request export within eligible ChatGPT settings or Privacy Portal; receive the download notification, retrieve the ZIP securely, then import directly through the Gemini UI.
- **Claude -> Gemini (manual one-time)**: export from Claude web/Desktop Settings -> Privacy using the account's export feature, download the export, then import the supported ZIP into Gemini directly. Claude's own personal-account exports cannot be imported as a full restored history into another personal Claude account.
- **Gemini destination**: Gemini's official help page documents **Settings -> Import memory to Gemini -> Import chats -> Add**; personal Google account, age **18+**, and eligible region. The help page explicitly excludes EEA, Switzerland and UK, and does not offer this in work/school/supervised Google accounts. It lists **5 GB maximum per ZIP**, up to **5 ZIPs daily**, and imports may take up to a day or become partial. Exact current UI options/eligibility must be checked by the user.
- **Privacy warning**: Google states imported/continued chats are saved in Activity and may be used to improve its services, including training. This is an important data-flow change. The owner must decide whether sending another provider's historical conversations into their Google account is acceptable. **Do not import private, professional, sensitive or client chats casually.**

Source links (official primary documentation):
1. [OpenAI ChatGPT export](https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data)
2. [OpenAI exports as reference are not native sidebar restoration](https://help.openai.com/en/articles/9106926-transfer-exported-conversations-between-chatgpt-accounts)
3. [Anthropic Claude data export](https://support.claude.com/en/articles/9450526-export-your-claude-data)
4. [Google Gemini native import](https://support.google.com/gemini/answer/16868299?hl=en)
5. [Google Gemini export via Takeout](https://support.google.com/gemini/answer/16920332?hl=en)

These documents do not collectively establish any unattended third-party automatic consumer conversation read/write API. Provider features can change; the documentation review timestamp is 2026-11-05.

## Code delivered

- `varyn/native_history_import.py`: pure, offline state machine for exactly two **supported source -> Gemini** directions. Pinned official source-help and destination URLs. Four separate acknowledgements: adult personal account, supported region, export ZIP ready, Google data-use understanding. Immutable, tokenized 90-second owner-review preview with replay/tamper/stale/changed-consent refusal. A successfully requested system-browser launch is **only a launch request**, never proof of provider account login, ZIP upload, import completion or native sync. Fixed owner-result values remain **UNVERIFIED**. Reset clears the entire session.
- `varyn/native_history_import_gui.py`: a separate scrollable Tk window within the 17S-28 workbench. User chooses source, reviews official provider export instructions, explicitly acknowledges the account/region/ZIP/privacy constraints, receives a full scrollable warning and approval before opening `https://gemini.google.com/`. Optional owner-reported result remains strictly in RAM and cannot authorize new permissions.
- `varyn/official_relay_workbench.py`: one new prominent button to open the guide, preserving the original reviewed manual chat relay and three-hop bounds. The guide does **not** open or parse ZIP files, record ZIP paths, request credentials, extract browser cookies, read account history, upload data, create provider conversations, or access paid model APIs.
- `tests/test_native_history_import.py`: source allowlist, official URLs, all four explicit acknowledgements, immutable preview, expiry, stale/replay, changed privacy, failure, false authority flags and reset. 
- `tests/test_native_history_import_tk.py`: hosted Windows **real Tk widgets** with mocked user consents and browser return values. It tests default no action, native help URL, accepted native Gemini browser request, self-report remains unverified, refused consent and nested source/privacy changes. These UI tests do **NOT** observe actual owner clicks or any provider-side data migration.
- Dedicated early Windows/Ubuntu CI gate and Windows-only Tk gate are required; a new Windows portable artifact should be published only after full regression and frozen EXE smoke success on the **exact final HEAD**.

## How to use without giving VARYN private data

1. Launch the latest verified `varyn-windows-portable` artifact normally (not as Administrator; do not disable Windows security protections for an unsigned binary). The focused manual workbench opens on its own.
2. Click **17S-30 | Official one-time ChatGPT/Claude ZIP import to Gemini**, choose source, then click **Read OFFICIAL export instructions** and approve opening the provider help URL.
3. Request and download your ZIP directly from that provider. Leave the export in your custody. **Do not select it inside VARYN or share it with this chat.** For first-run testing, you can inspect the guide without uploading anything.
4. Confirm the four eligibility/ZIP/privacy gates, inspect the full warning and click **Review and open official Gemini import page**. This opens only a pinned homepage; it does not upload any file.
5. In your actual Gemini account, find the provider-native import control and choose the ZIP **there**. Treat any Google privacy or partial-import prompt as independent and binding. Do not assume VARYN can report or undo its result.
6. Optionally record the fixed result as a **self-report** (uploaded/partial/failed/not checked). It lives only in local RAM until reset or app exit; no credentials, file paths, transcripts or uploaded account data are stored.

## Explicit blockers and stop conditions

The native import is supported only for eligible accounts. If Gemini has no import UI for the actual account or region, **stop**: VARYN does not bypass region/age restrictions. If a file contains sensitive private content that should not be sent to Google, do not upload it. If the official service changes the flow, use its latest documentation rather than VARYN's static guide. Do not claim a native import succeeded unless the owner actually sees it, and even then distinguish **self-report** from independently verified provider state.

The seven Option C requirements in `varyn/option_c_gate.py` remain BLOCKED: provider-published consumer history read/write APIs for all apps, account scopes, change detection, conflict/deletion semantics, privacy eligibility, and an owner-verified end-to-end *bidirectional* test remain unmet. This stage deliberately **does not change those gates**.
