"""Checkpoint 17H: reviewed OFFLINE consumer-app capability evidence.

This is a static, source-linked decision matrix, not a connector. It makes
no HTTP requests, stores no secrets and never grants provider-app access.
A provider model API is NOT a consumer ChatGPT/Claude/Gemini history API.
"""
from types import MappingProxyType

_AS_OF = "2026-11-04"
_UNKNOWN = "not_verified"
_DOCUMENTED = "documented_manual"
_RESTRICTED = "documented_manual_with_eligibility"
_EXPERIMENTAL = "documented_experimental_manual"
_NOT_SUPPORTED = "documented_not_supported"
_REFERENCE_ONLY = "reference_upload_not_restored_as_history"

# Official, publicly documented user-facing features (not third-party scripts).
# A manual import is deliberately NOT evidence of automatic synchronization.
_RECORDS = MappingProxyType({
    "chatgpt": (
        _DOCUMENTED, _UNKNOWN, _REFERENCE_ONLY,
        (
            "https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data",
            "https://help.openai.com/en/articles/9106926-transfer-exported-conversations-between-chatgpt-accounts",
        ),
        "Exports can be delayed; uploaded exports are reference material, "
        "not restored sidebar conversations. Account/workspace eligibility applies.",
    ),
    "claude": (
        _DOCUMENTED, _EXPERIMENTAL, _NOT_SUPPORTED,
        (
            "https://support.claude.com/en/articles/9450526-export-your-claude-data",
            "https://support.claude.com/en/articles/12123587-import-and-export-your-memory-from-claude",
            "https://support.claude.com/id/articles/8114491-mulai-dengan-claude",
        ),
        "Memory import is experimental and may omit details; no full "
        "cross-provider chat-history import. Export rules vary by plan.",
    ),
    "gemini": (
        _DOCUMENTED, _RESTRICTED, _RESTRICTED,
        (
            "https://support.google.com/gemini/answer/16920332?hl=en",
            "https://support.google.com/gemini/answer/16868299?hl=en",
        ),
        "Official Gemini Apps offers memory and full chat-history import "
        "from other platforms for eligible personal accounts; restrictions "
        "include age and region. No unattended sync is established.",
    ),
})


def official_app_evidence(provider):
    """Return a fresh JSON-compatible summary of public features and blockers."""
    if type(provider) is not str or provider not in _RECORDS:
        raise ValueError("Unknown official consumer app provider")
    exported, memory_import, history_import, sources, limits = _RECORDS[provider]
    return {
        "format": "varyn.official_app_evidence.v1",
        "provider": provider,
        "reviewed_as_of": _AS_OF,
        "manual_export_status": exported,
        "manual_memory_import_status": memory_import,
        "manual_chat_history_import_status": history_import,
        "official_consumer_history_read_api": _UNKNOWN,
        "official_consumer_history_write_api": _UNKNOWN,
        "automatic_bidirectional_consumer_sync": False,
        "model_api_proves_consumer_history_access": False,
        "manual_import_is_automatic_sync": False,
        "automatic_network_operations": 0,
        "can_dispatch": False,
        "official_sources": list(sources),
        "limitations": limits,
    }


def all_official_app_evidence():
    return {
        "format": "varyn.official_app_evidence_index.v1",
        "reviewed_as_of": _AS_OF,
        "providers": [official_app_evidence(p) for p in sorted(_RECORDS)],
        "automatic_bidirectional_consumer_sync": False,
        "can_dispatch": False,
    }
