"""17I: strict Option-C feasibility gate for official consumer-app sync.

OFFLINE diagnostics only. Neither a user claim of manual import, nor an API
model response, nor a synthetic test can authorize official consumer history
read/write. An explicitly reviewed NEW connector is required for real access.
"""
import argparse
import json

from varyn.official_app_evidence import official_app_evidence

_REQUIRED = (
    ("consumer_history_read_api", "Provider-published read API for existing signed-in consumer-app chats"),
    ("consumer_history_write_api", "Provider-published write API targeting that same consumer account history"),
    ("account_authorization", "Documented account consent, scopes, expiry and revocation for both directions"),
    ("change_detection", "Supported change capture and stable remote identifiers/revisions"),
    ("conflicts_and_deletions", "Tested tombstone, conflict, duplicate, retry and echo-loop semantics"),
    ("privacy_and_eligibility", "Provider terms, privacy and account/region eligibility checked"),
    ("owner_end_to_end", "Owner-accepted bidirectional create/update/delete tested using official apps"),
)
_PROVIDERS = ("chatgpt", "claude", "gemini")


def provider_option_c_gate(provider):
    """Unverified evidence remains a BLOCK even if manual imports exist."""
    if type(provider) is not str or provider not in _PROVIDERS:
        raise ValueError("Unknown official consumer-app provider")
    evidence = official_app_evidence(provider)
    requirements = []
    for key, description in _REQUIRED:
        if key == "consumer_history_read_api":
            status = evidence["official_consumer_history_read_api"]
        elif key == "consumer_history_write_api":
            status = evidence["official_consumer_history_write_api"]
        else:
            status = "not_verified"
        # This implementation only recognizes verified facts after a separate
        # reviewed connector, not booleans supplied through a config file.
        requirements.append({
            "gate": key, "status": status, "required_evidence": description
        })
    return {
        "format": "varyn.consumer_sync_proof_gate.v1",
        "provider": provider,
        "evidence_reviewed_as_of": evidence["reviewed_as_of"],
        "manual_memory_import": evidence["manual_memory_import_status"],
        "manual_history_import": evidence["manual_chat_history_import_status"],
        "requirements": requirements,
        "blocker_count": sum(x["status"] != "verified" for x in requirements),
        "status": "blocked_pending_provider_authority",
        "official_consumer_history_read_verified": False,
        "official_consumer_history_write_verified": False,
        "automatic_two_way_sync_verified": False,
        "can_dispatch": False,
        "requests_performed": 0,
        "external_provider_connected": False,
        "owner_gui_self_report_is_provider_authority": False,
        "model_api_can_substitute": False,
    }


def full_option_c_gate():
    providers = [provider_option_c_gate(p) for p in _PROVIDERS]
    return {
        "format": "varyn.option_c_full_gate.v1",
        "providers": providers,
        "provider_count": len(providers),
        "providers_verified": 0,
        "status": "blocked_pending_official_consumer_history_interfaces",
        "can_dispatch": False,
        "automatic_bidirectional_three_app_sync": False,
        "provider_requests_performed": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline proof requirements for ChatGPT+Claude+Gemini consumer sync"
    )
    parser.add_argument("--provider", choices=_PROVIDERS)
    args = parser.parse_args(argv)
    report = (provider_option_c_gate(args.provider) if args.provider
              else full_option_c_gate())
    print(json.dumps(report, sort_keys=True))
    # Exit 0 means the diagnostic executed, NOT that sync became ready.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
