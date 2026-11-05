"""17S-14 OFFLINE AppContainer one-shot child, no provider/network access.

Called only by the ephemeral GitHub Actions experiment, with five fixed
synthetic paths prepared by the privileged test parent. Never serves requests
in a loop, executes shell commands, or reads a real personal document.
"""
from pathlib import Path
import sys


def main(argv):
    if len(argv) != 5:
        return 90
    granted, denied, request, response, key = argv
    try:
        with open(granted, "rb") as handle:
            if handle.read(64) != b"varyn-17s13-granted":
                return 81
    except Exception:
        return 82
    try:
        with open(denied, "rb") as handle:
            handle.read(1)
        return 83  # Owner-only read unexpectedly succeeded.
    except PermissionError:
        pass
    except FileNotFoundError:
        return 84  # Missing file is NOT evidence of isolation.
    except Exception:
        return 85

    try:
        # -I -S intentionally strips ambient import paths. Only this
        # carefully copied source directory is explicitly approved.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from bounded_broker_protocol import offline_child_once
        offline_child_once(request, response, key)
    except Exception:
        return 86
    return 73


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
