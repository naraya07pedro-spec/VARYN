# Alpha 10: original service logos and fewer dead-end connection steps

Product changes made in response to the owner's actual Windows screenshot on 2026-11-06.

## Authentic, offline logos

The **Apps** page uses sourced and license-documented SVG artwork (SuperTinyIcons MIT, Simple Icons CC0, Devicon MIT, Gilbarbara Logos CC0), rasterized during the Linux build to **48×48 PNG** and packaged inside the Windows portable executable. This removes the prior fake circular initials for twenty known services including GitHub, Notion, Telegram, WhatsApp, Google apps, Netlify, Supabase, Canva, Descript and others. Unsupported/missing brands use neutral fallback: **never claim it is the official logo**. No remote image fetch, trackers, or brand API dependency. See `assets/BRAND-LICENSES.md`.

Important: brand symbols remain trademarks owned by their rights holders. Icon presence **does not imply authorization, a live app connection, or an endorsement**.

## Account onboarding

Supported independent API connections: **GitHub, Notion, Netlify, Supabase**, all **read-only within VARYN**. Open Apps → service → Connect → Create token (opens provider page) → paste token into local dialog → Connect. A verified API response is required before the app marks Connected. Click Browse to open a bounded read-only resource list and Disconnect to forget this in-RAM credential. Token privilege may be broader at its issuer; use least-privileged scopes where available.

**Telegram:** Bot token from `@BotFather` and numeric owner Telegram user ID, then Connect. This is a running-PC-only bot with explicit `/ask` and `/confirm` for each external model request. Model API key previously entered in VARYN is reused in process RAM. No silent chat syncing and no 24/7 availability.

Other applications including **Gmail, Google Calendar, Google Drive, WhatsApp and LinkedIn** have **NO authenticated VARYN adapter** in Alpha 10. An **Official guide** action opens verified developer documentation in one click. Where no guide exists, a **Request connector** link opens a GitHub issue draft. The 'View setup' confirmation-popup dead end is removed. The app directory no longer mixes unrelated skill/plugin candidates with named app accounts. Do not paste credentials into unsupported flows.

The user asked for less setup friction. Most provider authentication is outside VARYN's control; a genuinely one-click OAuth flow requires registering a specific OAuth application with the provider, configuring scopes and redirect URI, and having the owner grant access. Claiming it already works would be dishonest.

## Desktop and release verification

The PNG creation step runs on Ubuntu with CairoSVG; no Cairo library or Python is needed on the user's PC. The Windows PyInstaller command embeds the generated PNG assets. Frozen EXE smoke explicitly checks that five logos decode as 48×48 Tk PhotoImages while all existing model/privacy guards and DPAPI verification continue.

The release CI uses the targeted Windows Tk / Python / API adapter test gate and frozen portable checks. The former exhaustive research suite remains available via manual workflow dispatch, not silently reported as passed.

No real-user OAuth, GitHub, Notion, Netlify, Supabase, Telegram or WhatsApp account was accessed in development. A successful build is not evidence that the owner's live credentials work. Binary is unsigned, experimental, and not production certified. VPS deployment remains excluded at owner's request.
