# VARYN Alpha 11: genuine Google workspace + Hostinger mail connections

**Product intent:** Replace More services → Official guide dead ends with genuine owner-controlled connection flows for four specific services, without inventing access to existing ChatGPT plugins.

## Gmail, Google Calendar, Google Drive

All three have real **Connect / Browse / Disconnect** buttons in Apps > More services. Clicking Connect opens a VARYN dialog that accepts an **OAuth 2.0 Desktop application client JSON** created by the owner from Google Cloud Console. This is necessary because VARYN is not registered as a verified Google OAuth client for general public distribution; an app cannot simply inherit browser sessions or another ChatGPT plugin's credentials.

### One-time setup

1. Open https://console.cloud.google.com/apis/credentials and create an **OAuth client of application type: Desktop app**. Download its JSON. Keep the JSON private; do not paste it into ChatGPT, GitHub or public issues. Configure the OAuth consent screen, and add your account to the test-user list if Google requests it.
2. Enable **Gmail API**, **Google Calendar API** and **Google Drive API** in that Google Cloud project. Google may require separate app verification for restricted Gmail/Drive scopes when distributing publicly. Some organizational accounts may forbid these scopes.
3. In VARYN Apps → Gmail/Calendar/Drive **Connect** → **Choose JSON and sign in**. VARYN opens the **system browser on Google's own sign-in page**, requests explicit read-only scope consent, receives the authorization code through a listener bound only to `127.0.0.1` and validates a one-time anti-CSRF state and PKCE S256 verifier. The receiver closes after completion or timeout.
4. The same Google account session enables browse-only views for all three services. **Browse** shows up to 8 Gmail subject/sender metadata records, 20 calendars or 20 Google Drive file names (no downloads). Double-click opens the official app in your own browser.
5. **Disconnect** clears the local access and refresh tokens from this process. **Tokens remain in RAM only** and a restart requires approval again. No browser cookies, passwords, token JSON or emails are written to VARYN files or GitHub.

Requested OAuth scopes:
- `openid email` to identify which Google account actually authorized VARYN.
- `https://www.googleapis.com/auth/gmail.readonly` (RESTRICTED).
- `https://www.googleapis.com/auth/calendar.calendarlist.readonly`.
- `https://www.googleapis.com/auth/drive.metadata.readonly` (RESTRICTED).

Google's consent screen may block the authorization until required APIs, scopes, testing status and verification are configured. This is an actual provider rule and cannot be bypassed by VARYN. Do **not** disable your browser security protections or upload any credentials to VARYN's GitHub.

**Technical limits:** No Gmail send/delete/modify, no calendar event create/update, no Drive file download/edit/share, no Google Docs/Sheets authoring, no background sync and no sending the content to the language model. Gmail browse requires additional bounded metadata GETs. Revoking Google OAuth grants is done via https://myaccount.google.com/permissions, distinct from disconnecting VARYN's in-memory session. Google user response and URLs are untrusted and parsed/limited.

## Hostinger Email

Apps → Hostinger Mail → **Connect** opens a real **email + mailbox password** input. VARYN authenticates only to the official `imap.hostinger.com:993` with system-trusted SSL certificates, runs `EXAMINE`/readonly inbox checks, and can list up to 12 email subject/from headers with `BODY.PEEK` without marking messages read. Credentials stay only in the running VARYN process memory and are dropped on Disconnect/exit. No SMTP, mail sending, background polling, email import to AI, password reuse from ChatGPT or permanent storage.

This is for **Hostinger Email** (not Titan Email or Microsoft 365). Official configuration reference: https://support.hostinger.com/en/articles/1575756-how-to-get-email-account-configuration-details-for-hostinger-email

## Source and safety

- `varyn/google_oauth.py`: official desktop OAuth PKCE, strict loopback callback, userinfo verification, provider-pinned token refresh and read-only resource browsing.
- `varyn/hostinger_imap.py`: pinned Hostinger IMAP TLS, verified account login, readonly mailbox, bounded headers, no write operations.
- `varyn/external_connect_ui.py`: Tk Connect / Browse / Disconnect flows, all network work off UI thread.
- `varyn/app_hub_ui.py`: real More services buttons; unsupported connectors retain honest instructions.
- `tests/test_google_hostinger_alpha11.py`: local simulated OAuth/IMAP/metadata checks, no production secrets or account access.
- Native Windows Tk tests assert actionable controls exist.

**CI evidence is not evidence of live Google authorization or Hostinger mailbox login with the owner's account.** These remain unverified until the user explicitly connects in the Windows release. No VPS changes, no developer-owned shared OAuth credential, no automatic access to external accounts.

Other entries such as WhatsApp, LinkedIn, Canva and Descript still require their own supported authentication adapters; their current guide links must not be interpreted as live connections. Actual no-code 'Sign in with Google' for all users would require VARYN to operate its own registered and verified Google OAuth application, which is outside an unsigned experimental public alpha.
