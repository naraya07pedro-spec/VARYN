# VARYN alpha.4 | Dark workspace redesign

Owner screenshot feedback (2026-11-06 WIB) showed a mostly unstyled Tkinter form, cramped controls, a large text log and a non-obvious product identity. This revision changes the **actual Windows desktop UI**, not a website or mockup.

## UI changes
- New slate/navy dark visual system and purple brand accent.
- Wider 1170 × 760 main window, left sidebar for AI Chat, My Tasks, and Connectors & Skills, and clearer active navigation.
- Rebuilt chat layout: headline, model selector, status card, scrollable conversation area, high-contrast message composer, purple Send button and Ctrl+Enter shortcut.
- Rebuilt task and integrations panels with aligned spacing, headings, dark treeviews, and task actions.
- Does not change provider gateway, billing policy, local task persistence, OAuth permissions or fake model behavior. The familiar settings and per-request approval remain.
- Uses only standard Tk/ttk. No external UI asset, remote resource, runtime font download or proprietary dependency. No image has been synthesized and presented as an actual application screenshot.

## Limitations
This remains a Windows alpha and desktop UI, not a hosted browser app. Tested Windows CI screenshots are not provided as if captured on the owner's PC. The real provider requires separate API credentials and explicit human review of each request. Task execution and authenticated external app connectors are still incomplete.

## Shipping gate
The exact source will be published as v0.1.0-alpha.4 **only if** Windows and Ubuntu unit tests, frozen portable GUI checks and release packaging succeed. Until verified, the published alpha.3 remains the current release. PR #1 stays open/draft; main source is not merged.
