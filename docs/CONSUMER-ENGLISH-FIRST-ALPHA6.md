# VARYN Consumer UX, English-first | Windows Alpha 6

Date: 2026-11-06. This update responds directly to real owner-device feedback on the Alpha 5 screenshot: mixed English/Indonesian text, non-maximizable window, and a generated-looking scenic/Tk dashboard.

## Design decisions and implementation

- The **default language is English** throughout the primary VARYN consumer shell, task manager, history, app catalog, chat prompt, model selection and settings.
- The header contains a real language selector: **English, Bahasa Indonesia, Español, Français**. Changes occur **immediately in the existing UI**, with the task database and current conversation still open. The choice is saved separately in `%LOCALAPPDATA%\\VARYN\\preferences.json` as only a language code. If saving fails, the active language still changes for the current session.
- Old engineering tools reachable through Advanced remain English-language interfaces; warning text and real provider responses are not machine-translated. This is **primary-workspace localization**, not a claim of complete third-party/API/legacy system translation.
- Removed the AI-style purple mountain artwork and fake sci-fi cards from normal startup. The new default is a calm **warm, minimal editorial workspace** with ordinary Segoe UI typography, content-led hierarchy and simple navigation rows rather than illustrations. There is no generated image, downloaded font, stock hero or sci-fi branding.
- Chat remains a real request-to-model gateway with the existing explicit per-request review, no provider credentials inherited from ChatGPT, no automatic retries, no deceptive AI simulation. The offline-only mode is clearly disclosed.
- The application is **not a transient popup** anymore: removed `OwnerHome.transient(desktop)`, added true resizable native Toplevel behavior, and added an obvious **Maximize / Restore** control in the header. On Windows it initially opens maximized, and owners can restore and resize it normally. The settings popup may remain modal.
- Tasks continue to save to unencrypted local SQLite; no automatic task execution and no authenticated app connectors are implied.
- Refined task statuses and app candidate status labels are translated in the visible tables without changing stored database schema or API behavior.
- The original Alpha 5 design source is kept in Git history; Alpha 6 is a deliberate, feedback-driven visual replacement.

## Code & verification

The source includes `varyn/ui_language.py` (complete primary UI translations and harmless preference persistence), `varyn/consumer_chat.py` (working editorial chat), `varyn/consumer_workspace.py` (maximize and language controls), and Windows-hosted local GUI tests.

Only publish `v0.1.0-alpha.6` after the exact source commit's Windows and Ubuntu unit tests, Windows PyInstaller EXE creation and GitHub release publishing all complete successfully. **Do not claim** a screenshot-perfect render or real-owner PC acceptance based solely on CI. Source remains in the OPEN/DRAFT PR #1, with no merge into `main`.

## Limitations

VARYN remains an **unsigned experimental Windows application**. Live model usage requires owner-controlled API keys and permission reviews; billing is not provider-enforced by this UI. No native ChatGPT/Claude/Gemini app history sync, no automatic Gmail/Drive/Notion access, and no 24/7 autonomous task execution.
