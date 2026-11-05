"""17S-14: offline one-request/one-response broker protocol, NOT production IPC.

All data is synthetic. No network, filesystem access tools, model context,
provider keys, shell commands or user-controlled Python execution. The HMAC
authenticates envelope bytes to a single ephemeral parent/child trial only;
a secret placed inside shared AppContainer storage is NOT a production
authentication boundary against a malicious child or same-user host process.
"""
import hashlib
import hmac
import json
import secrets
import time

VERSION = "varyn.broker.synthetic.v1"
ACTION = "sum_synthetic_counts"
MAX_BYTES = 2048
TTL_SECONDS = 20


class BrokerRejected(ValueError):
    """A bounded, generic error that never contains untrusted input."""


def _unique_pairs(pairs):
    data = {}
    for k, v in pairs:
        if k in data:
            raise BrokerRejected("Duplicate JSON field")
        data[k] = v
    return data


def strict_json(raw):
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise BrokerRejected("Envelope size rejected")
    try:
        v = json.loads(raw.decode("utf-8", "strict"),
                       object_pairs_hook=_unique_pairs,
                       parse_constant=lambda value: (_ for _ in ()).throw(
                           BrokerRejected("Nonfinite JSON rejected")))
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise BrokerRejected("Invalid broker JSON") from None
    if type(v) is not dict:
        raise BrokerRejected("Broker envelope must be object")
    return v


def canonical(obj):
    try:
        raw = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise BrokerRejected("Invalid broker envelope") from None
    if len(raw) > MAX_BYTES:
        raise BrokerRejected("Broker envelope too large")
    return raw


def _hex_token(s):
    return (type(s) is str and len(s) == 32
            and all(c in "0123456789abcdef" for c in s))


def _check_key(key):
    if type(key) is not bytes or len(key) != 32:
        raise BrokerRejected("Invalid ephemeral broker key")


def _mac(envelope, key):
    _check_key(key)
    return hmac.new(key, canonical(envelope), hashlib.sha256).hexdigest()


def _check_mac(signed, key):
    if type(signed) is not dict or type(signed.get("mac")) is not str:
        raise BrokerRejected("Unsigned broker envelope")
    fields = dict(signed)
    digest = fields.pop("mac")
    if not hmac.compare_digest(_mac(fields, key), digest):
        raise BrokerRejected("Broker authentication rejected")
    return fields


def _payload(payload):
    if type(payload) is not dict or set(payload) != {"counts"}:
        raise BrokerRejected("Unrecognized synthetic data fields")
    values = payload["counts"]
    if (type(values) is not list or not 1 <= len(values) <= 12
            or any(type(v) is not int or not 0 <= v <= 10000 for v in values)):
        raise BrokerRejected("Synthetic count bounds rejected")
    return values


def new_request(key, counts, *, now=None):
    _check_key(key)
    values = _payload({"counts": counts})
    moment = int(time.time()) if now is None else now
    if type(moment) is not int or moment < 1:
        raise BrokerRejected("Invalid broker timestamp")
    envelope = {
        "version": VERSION, "type": "request", "action": ACTION,
        "request_id": secrets.token_hex(16),
        "nonce": secrets.token_hex(16),
        "issued_at": moment,
        "payload": {"counts": list(values)},
    }
    return {**envelope, "mac": _mac(envelope, key)}


def authenticate_request(signed, key, *, now=None):
    fields = _check_mac(signed, key)
    if set(fields) != {
        "version", "type", "action", "request_id",
        "nonce", "issued_at", "payload",
    }:
        raise BrokerRejected("Unknown broker request fields")
    if (fields["version"] != VERSION or fields["type"] != "request"
            or fields["action"] != ACTION):
        raise BrokerRejected("Broker action/version rejected")
    if not _hex_token(fields["request_id"]) or not _hex_token(fields["nonce"]):
        raise BrokerRejected("Bad broker request identity")
    moment = int(time.time()) if now is None else now
    if type(moment) is not int or type(fields["issued_at"]) is not int:
        raise BrokerRejected("Broker clock is invalid")
    age = moment - fields["issued_at"]
    if not 0 <= age <= TTL_SECONDS:
        raise BrokerRejected("Expired or future broker request")
    _payload(fields["payload"])
    return fields


def execute_fixed_action(verified):
    if (type(verified) is not dict or verified.get("action") != ACTION
            or verified.get("type") != "request"):
        raise BrokerRejected("Action not permitted")
    return sum(_payload(verified.get("payload")))


def new_response(request, answer, key):
    if (type(request) is not dict
            or request.get("type") != "request"
            or not _hex_token(request.get("request_id"))
            or not _hex_token(request.get("nonce"))
            or type(answer) is not int or not 0 <= answer <= 120000):
        raise BrokerRejected("Response input rejected")
    envelope = {
        "version": VERSION, "type": "response",
        "request_id": request["request_id"],
        "nonce": request["nonce"], "status": "ok", "total": answer,
    }
    return {**envelope, "mac": _mac(envelope, key)}


class OneShotReplyVerifier:
    def __init__(self, request, key):
        self._request = authenticate_request(
            request, key, now=request.get("issued_at"))
        self._key = key
        self._consumed = False

    def consume(self, raw):
        if self._consumed:
            raise BrokerRejected("Broker response replay rejected")
        # Even failed/forged attempts consume this verifier, so no automatic
        # retry of a dispatched tool operation can occur.
        self._consumed = True
        fields = _check_mac(strict_json(raw), self._key)
        if set(fields) != {
            "version", "type", "request_id", "nonce", "status", "total",
        }:
            raise BrokerRejected("Unexpected broker response fields")
        if (fields["version"] != VERSION or fields["type"] != "response"
                or fields["request_id"] != self._request["request_id"]
                or fields["nonce"] != self._request["nonce"]
                or fields["status"] != "ok"):
            raise BrokerRejected("Broker correlation rejected")
        total = fields["total"]
        if type(total) is not int or not 0 <= total <= 120000:
            raise BrokerRejected("Invalid broker result")
        # This comparison is a synthetic oracle, NOT a real worker trust
        # guarantee or production confidentiality mechanism.
        if total != execute_fixed_action(self._request):
            raise BrokerRejected("Broker result inconsistent")
        return total


def offline_child_once(request_file, response_file, key_file):
    """Child-side deterministic single operation, never a loop or shell."""
    from pathlib import Path
    key = Path(key_file).read_bytes()
    _check_key(key)
    with open(request_file, "rb") as file:
        raw = file.read(MAX_BYTES + 1)
    request = authenticate_request(strict_json(raw), key)
    result = new_response(request, execute_fixed_action(request), key)
    # Exclusive create rejects pre-existing/stale responses.
    with open(response_file, "xb") as file:
        file.write(canonical(result))
    return 0
