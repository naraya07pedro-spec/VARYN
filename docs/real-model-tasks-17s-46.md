# VARYN 17S-46 | Real owner-typed tasks through the Model Control Center

Date: 2026-11-06 (WIB).

## Capability now implemented
The real user can replace the default fictional SYNTHETIC: test prompt with their own question in the Windows Model Control Center. With the correct provider API key in the **local owner-PC process** and an explicitly reviewed model/price, the user can authorize ONE outbound inference. A real prompt that does not begin with SYNTHETIC: requires an independent **owner real-task checkbox**; the exact full request is then shown through the established reviewed-content callback for a second decision. Neither checkbox nor network permission is enabled by default.

The reviewed request includes the full owner-typed task, chosen model, fixed provider, estimated input tokens, maximum requested output tokens, quoted price date and non-enforced estimated cost. It makes no claim about actual pricing, provider identity or authenticated account ownership.

## Runtime behavior
- `varyn/gateway_chat.prepare` now supports `allow_real_task=True`; by default it still accepts only SYNTHETIC: tasks. Bounds: nonempty, at most 4,000 characters, 16–2,048 requested output tokens, no control characters other than CR/LF/TAB.
- `varyn/universal_gateway.UniversalGateway.generate` forwards `allow_real_task` only from an explicit caller flag. Fresh per-request `approve_request=True`, model/price eligibility, no obvious credential shapes, provider key, network policy and local budget checks all remain.
- `varyn/model_control_center.ModelControlCenter` adds a real-task checkbox, includes it in the pre-/post-review snapshot comparison, and resets it OFF after approval. A rejected review does not dispatch or consume budget. The worker gets exactly one task-mode flag and never automatically retries.
- Answers remain volatile in the GUI. No remembered conversations, local file injection, automatic tools, background orchestration, provider failover, private customer data import or official consumer ChatGPT/Claude/Gemini sync is added.
- `README-PORTABLE.txt` describes use from the shipped Windows app. Four new files/modified source files are shipped through the existing Windows Portable workflow when CI succeeds.

## User-facing sequence
1. Launch current VARYN Portable as a normal Windows user, using the owner pilot launcher and a genuine API key entered locally for the chosen provider (OpenRouter or DeepSeek; 9Router requires explicit upstream authorization).
2. Open **17S-40 | Open Model Control Center** in the main window. Discover or manually enter an actual model ID. Independently inspect its current price and access in the provider console; register both reviewed rates.
3. Replace the default SYNTHETIC: sample with your own short, nonsensitive question. Check **Authorize MY typed non-synthetic text for ONE reviewed request**.
4. Enable the model network toggle, choose input/output estimate and a conservative price ceiling, then **Review exact request & send ONCE**. Inspect exactly what leaves the PC and approve once.
5. The answer appears in this window. Subsequent real tasks need fresh real-task and network permission again. No model tool is authorized to take actions in other apps.

## Verification scope and limitations
Focused tests cover real-input default denial, separately required opt-in and approval, no quota consumption when denied, and secret-pattern refusal. Existing CI continues to run. At commit time DO NOT claim updated Windows/Ubuntu CI or portable artifact success until GitHub Actions confirms the exact commit. No real API keys, owner-PC provider connections or billing have been verified by this change.

**PR #1 stays OPEN/DRAFT, main unchanged. Option C native automatic two-way official consumer-app synchronization still BLOCKED.**
