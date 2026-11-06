# VARYN Alpha 3: Chat-first Windows UI

This update responds to owner feedback: opening a chatbot should not require navigating a technical pricing panel. The Windows application now displays a message composer and chat transcript immediately.

**Offline demo:** clearly marks every response as a simulation, with zero provider calls. It is not a real AI model.

**Live providers:** OpenRouter and DeepSeek require a separately entered API credential, a once-per-session reviewed model ID and price setup, and fresh approval of the exact outgoing request each time. The resulting answer appears in the chat transcript. The model price estimate does not cap provider charges. A chat request contains only the new prompt, not all previous messages.

My Tasks and Connectors / Skills remain separate tabs. Task execution, third-party account authorization, native consumer account history sync and 24/7 hosted service are not implemented.

Windows packaging targets the new experimental v0.1.0-alpha.3 pre-release only after its exact CI run successfully publishes the ZIP. Do not claim it shipped until confirmed. The Windows package is unsigned and is not suited for sensitive customer data.
