# VARYN Alpha.2 | First-run Windows owner workspace

**Date:** 2026-11-06 (WIB). Branch: `feat/local-memory-prototype-20261103` (draft PR #1). The release exists **only after** GitHub Actions confirms the exact commit's published `v0.1.0-alpha.2` prerelease.

## Actual integrated startup

Opening the non-elevated `VARYN-Portable.exe` or the owner PowerShell launcher opens **VARYN Home**, with three tabs:

1. **Ask AI:** opens the existing Model Control Center, which can perform ONE live owner-reviewed request to OpenRouter, DeepSeek, or authorized 9Router with independent provider credentials. Fake-model trial works offline. It is not multi-step autonomous task execution or native app sync.
2. **My Tasks:** adds, lists, completes, pauses and cancels owner-local tasks in `%LOCALAPPDATA%\\VARYN\\tasks.sqlite3`. There is no application-defined ceiling on total number of stored tasks; SQLite, available disk and hardware remain finite. Task due status refreshes every 30 seconds while the desktop runs (up to 200 due tasks per pass). No external action, reminder, email or AI request is launched automatically. Tasks are UNENCRYPTED, so do not put private/customer content into titles.
3. **Connectors / Skills:** displays currently cataloged candidate names with explicit **NOT CONNECTED** status; no ChatGPT connector cookies/tokens/OAuth grants are imported. The Advanced Desktop remains accessible for the existing approved public GitHub metadata lookup and previous research features.

The earlier manual ChatGPT/Claude/Gemini copy/paste workbench is still accessible. The previous `--smoke-only` entrypoint does **not** start the owner home or touch user-local task data.

## Package and security gates

- GitHub Windows PyInstaller build bundles `integrations/catalog.json` explicitly as data, not as an executable plugin.
- CI tests remain on Windows and Ubuntu. Hosted Windows GUI smoke does not prove device/account acceptance.
- All model network calls remain gated by explicit model API key, typed prompt review, and owner approval. Quote estimates are not billing hard caps.
- The default local process does **not** run a 24/7 cloud scheduler; PC shutdown stops due checks. No real app credentials can be inherited from ChatGPT.
- The new alpha ZIP is UNSIGNED; do not disable Defender or SmartScreen to run it. It is not production-safe or a confidential-data vault.

## Honest current product scope

The application is usable as a local AI gateway + task tracker + integration directory **when the published release works on the owner's device**. It is NOT yet the user's full desired universal autonomous orchestration system with connected Gmail/Drive/Notion and automatic native ChatGPT/Claude/Gemini consumer history synchronization. Those depend on individually authorized, supported integrations and further engineering.

Do not merge draft PR #1 into `main` without explicit user authorization.
