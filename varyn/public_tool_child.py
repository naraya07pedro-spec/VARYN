"""17S-4: isolated-mode Python child for ONE public GitHub metadata read.

A separate OS process is NOT an OS sandbox; this child runs as the same user.
It receives only validated input on stdin, holds no provider credentials,
prints only bounded structured output and never accepts arbitrary URLs.
"""
import json
from pathlib import Path
import sys

# -I removes cwd/PYTHONPATH from imports; load only our fixed repo package root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from varyn.public_github_tool import (
    MAX_INTENT_BYTES, PublicToolRejected, fetch_public_repo_metadata,
    parse_public_tool_intent,
)


def main():
    if sys.argv[1:] == ["--offline-self-test"]:
        data = {"format": "varyn.public_tool_child.self_test.v1",
                "network_used": False, "isolated_mode": bool(sys.flags.isolated),
                "no_site": bool(sys.flags.no_site)}
        sys.stdout.buffer.write(json.dumps(data).encode("utf-8"))
        return 0
    if sys.argv[1:] == ["--offline-stdin-self-test"]:
        # Guard integration test: stay blocked until supervised stdin is sent.
        # No public network, credentials, or model actions are used.
        sys.stdin.buffer.read(MAX_INTENT_BYTES + 1)
        sys.stdout.buffer.write(json.dumps({
            "format": "varyn.public_tool_child.stdin_self_test.v1",
            "network_used": False,
            "isolated_mode": bool(sys.flags.isolated),
            "no_site": bool(sys.flags.no_site),
        }).encode("utf-8"))
        return 0
    if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site:
        return 2
    try:
        raw = sys.stdin.buffer.read(MAX_INTENT_BYTES + 1)
        if len(raw) > MAX_INTENT_BYTES:
            return 3
        repository = parse_public_tool_intent(raw.decode("utf-8", "strict"))
        result = fetch_public_repo_metadata(repository)
        output = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(output) > 4096:
            return 4
        sys.stdout.buffer.write(output)
        return 0
    except (ValueError, UnicodeError, PermissionError, OSError, PublicToolRejected):
        return 5
    except Exception:
        # Never forward exceptions, private environment values, or error bodies.
        return 6


if __name__ == "__main__":
    raise SystemExit(main())
