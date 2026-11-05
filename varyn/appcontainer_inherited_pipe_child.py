"""17S-16 CI-only AppContainer child: one bounded stdin/stdout exchange.

Does NOT know provider credentials, HMAC keys, real user files, network,
shell commands or arbitrary tool schemas. Uses stdin/stdout handles that
the OS inherited via PROC_THREAD_ATTRIBUTE_HANDLE_LIST.

Exit 73 requires a granted synthetic read, owner-only synthetic denial,
no inherited decoy handle and a single valid synthetic request/response.
"""
import ctypes
from ctypes import wintypes
import json
import sys

MAX_LEN = 512
ACTION = "sum_synthetic_counts"
VERSION = "varyn.anon-pipes.v1"


class Reject(ValueError):
    pass


def _pairs(pairs):
    seen = {}
    for k, value in pairs:
        if k in seen:
            raise Reject("duplicate field")
        seen[k] = value
    return seen


def _read_exact(n):
    out = sys.stdin.buffer.read(n)
    if len(out) != n:
        raise Reject("truncated pipe frame")
    return out


def _read_one():
    length = int.from_bytes(_read_exact(2), "big")
    if not 1 <= length <= MAX_LEN:
        raise Reject("request oversize")
    try:
        return json.loads(_read_exact(length).decode("utf-8", "strict"),
                          object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              Reject("nonfinite value")))
    except (ValueError, UnicodeError, RecursionError):
        raise Reject("invalid synthetic request") from None


def _hex32(value):
    return (type(value) is str and len(value) == 32 and
            all(c in "0123456789abcdef" for c in value))


def main(argv):
    if len(argv) != 3:
        return 90
    allowed, denied, decoy_raw = argv
    try:
        decoy = int(decoy_raw)
        if decoy < 4:
            return 91
    except Exception:
        return 111  # Cannot parse fixed synthetic decoy identity.
    try:
        k = ctypes.WinDLL("kernel32", use_last_error=True)
    except Exception:
        return 112  # Native library loader unavailable.
    try:
        k.GetStdHandle.argtypes = [wintypes.DWORD]
        k.GetStdHandle.restype = wintypes.HANDLE
        k.GetHandleInformation.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.GetHandleInformation.restype = wintypes.BOOL
        inherited_stdin = k.GetStdHandle(0xfffffff6)  # STD_INPUT_HANDLE
        positive_flags = wintypes.DWORD()
        if not inherited_stdin or not k.GetHandleInformation(
                inherited_stdin, ctypes.byref(positive_flags)):
            return 123  # The authorized pipe must exist as kernel handle.
    except Exception:
        return 124  # Cannot establish valid positive kernel control.
    try:
        decoy_flags = wintypes.DWORD()
        present = k.GetHandleInformation(decoy, ctypes.byref(decoy_flags))
        error = ctypes.get_last_error()
        if present:
            return 92  # Unlisted event was inherited despite handle list.
        if error != 6:  # ERROR_INVALID_HANDLE
            return 125  # Unrecognized kernel denial is not proof.
    except OSError as exc:
        # ctypes may surface an invalid handle as an OSError instead of
        # returning FALSE. Accept only the exact native WinError 6.
        if getattr(exc, "winerror", None) != 6:
            return 126
    except Exception:
        return 127

    try:
        with open(allowed, "rb") as resource:
            if resource.read(64) != b"varyn-17s13-granted":
                return 81
    except Exception:
        return 82
    try:
        with open(denied, "rb") as resource:
            resource.read(1)
        return 83
    except PermissionError:
        pass
    except FileNotFoundError:
        return 84  # non-existent private file is never security evidence
    except Exception:
        return 85

    try:
        payload = _read_one()
        if type(payload) is not dict or set(payload) != {
                "version", "action", "request_id", "nonce", "counts"}:
            return 94
        if (payload["version"] != VERSION or payload["action"] != ACTION or
                not _hex32(payload["request_id"]) or
                not _hex32(payload["nonce"])):
            return 95
        values = payload["counts"]
        if (type(values) is not list or not 1 <= len(values) <= 12 or
                any(type(v) is not int or not 0 <= v <= 10000 for v in values)):
            return 96
        result = {
            "version": VERSION, "request_id": payload["request_id"],
            "nonce": payload["nonce"], "status": "ok", "total": sum(values)}
        out = json.dumps(result, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("ascii")
        if len(out) > MAX_LEN:
            return 97
        sys.stdout.buffer.write(len(out).to_bytes(2, "big") + out)
        sys.stdout.buffer.flush()
        return 73
    except Exception:
        return 98


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
