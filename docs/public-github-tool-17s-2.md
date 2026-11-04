# VARYN Checkpoint 17S-2: Reviewed public GitHub tool execution

Date: 2026-11-04. Status: implementation; CI verification must be recorded for the final commit. The owner-selected consumer-app history sync **Option C remains unchanged**.

## Purpose

Move from 17S-1's fixed local demonstration to the first real, bounded **external** tool. In the desktop, a user may paste or review *untrusted* structured JSON requesting a public GitHub repository metadata lookup. The trusted desktop must separately opt into public GitHub network access, show the exact repository, destination and request digest, receive an individual yes/no approval, and then allow only one anonymous GET. Model-provided text and a granted tool have **different authority**.

GitHub documents that \`GET /repos/{owner}/{repo}\` can read public metadata without authentication. This implementation uses no GitHub token, no private GitHub account/session, and no write routes. It is subject to GitHub's unauthenticated rate limits (currently documented as 60 requests/hour per source IP), and the gateway additionally caps approved dispatch attempts to five **per desktop session**. This local cap is not a guaranteed upstream rate-limit allocation.

References:
- https://docs.github.com/en/rest/repos/repos#get-a-repository
- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api

## Specific implementation

- \`varyn/public_github_tool.py\` parses one strict UTF-8 bounded JSON object. Exactly three top-level fields, one \`repository\` argument, and one tool are accepted. Duplicate keys, free text, URLs, paths, extra flags, unknown tools, and injected approval properties are refused.
- Tool: \`github_public_repo_metadata\`. Endpoint: **fixed** \`https://api.github.com/repos/{owner}/{repository}\`, formed only after validating the owner/name characters. No user-supplied URLs, credentials, proxies, redirects, shell, filesystem access, model calls, repository writes, or automatic retries.
- \`PublicGithubToolGateway\` stores one-time review IDs and SHA-256 digests in RAM; the grant is consumed before attempting network access. Fresh network consent is checked **again** at dispatch. A denied action performs no request; a revoked consent blocks it; a failed network attempt still counts toward the five-attempt in-RAM budget.
- \`varyn/desktop.py\` adds a **separate** \`Allow public GitHub metadata reads\` checkbox. It is distinct from the existing AI-provider network consent, and OFF by default. A dedicated button reviews untrusted JSON pasted into the message field.
- The response must be a public repository matching the requested full name, with strict field types and size bounds. Only the following validated metadata are displayed: repository name, default branch, stars, open items (including PRs), archive status. Freeform description, remote URLs and arbitrary response fields are discarded to reduce prompt-injection propagation.
- The returned data are marked untrusted and shown **locally only**. The feature does not inject the result into an AI context or an agent task plan, and does not enable autonomous dispatch.
- No persistent credential, permission token, or response body is written to disk; the bounded audit shows only event names and counts.

## UI acceptance (explicitly non-private)

1. Launch Windows desktop as before, without personal data or provider credentials.
2. Leave **Allow public GitHub metadata reads** disabled. Paste the JSON below in the Message field and click **Review public GitHub tool intent (JSON, network)**. It must refuse without a network request.
3. Enable the GitHub-specific checkbox. Click again. Review the repository and exact endpoint. Declining must perform no network request.
4. Approve one request. If public GitHub networking succeeds, metadata should display. If offline or rate-limited, it must stop without retries or a fake result.
5. Revoke the GitHub checkbox; subsequent requests must fail closed. An unrelated AI-provider checkbox must not authorize GitHub.

Input:

    {"format":"varyn.public_tool_intent.v1","tool":"github_public_repo_metadata","arguments":{"repository":"naraya07pedro-spec/VARYN"}}

## Tests, limits, and non-claims

- \`tests/test_public_github_tool.py\`: strict parser, injection, forbidden tools and URLs, decision binding, revocation, budget/denial/replay, mocked single-request HTTP, redirect blocking, content-type, body limits, private-result rejection, response field filtering, GUI headless callback. **No live internet is used in CI**.
- \`tests/test_public_github_tool_tk.py\`: hosted Windows real Tk button invocations with **mocked** fetcher, not physical human clicks or a live GitHub connection.
- The client uses a synchronous, five-second timeout. The Tk window may block briefly during a permitted GitHub request. Improving responsiveness with a cancellable UI-owned worker and robust lifecycle handling remains a separate task.
- User confirmation is still an asserted trusted Tk callback, **not authenticated human identity** or an OS-level sandbox. This does not authorize arbitrary personal files, write operations, or app automation.
- GitHub public metadata access is **not** ChatGPT/Claude/Gemini official consumer-app conversation history synchronization. Opsi C remains an externally blocked requirement, not replaced by this feature.

Next: measure one real **owner-approved** public metadata request on the owner's laptop and strengthen generic tool permission identity/worker isolation before any consequential, mutating or private-account tools. Do not promote 17S-2 to an entire universal tool system based on synthetic CI.
