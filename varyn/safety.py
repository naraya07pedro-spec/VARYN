"""Conservative heuristic secret guard for an UNENCRYPTED local prototype.

This is not DLP, encryption, authentication, or comprehensive secret scanning.
Do not log or echo rejected inputs. Existing stored secrets are not removed.
"""
import re


class SensitiveContentError(ValueError):
    """Input looks like a credential. No matching substring is exposed."""


_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", re.I),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}", re.I),
    re.compile(r"\b(?:password|passwd|api[_-]?key|access[_-]?token|secret[_-]?key)\s*[:=]\s*[\"']?[^\s,\"']{8,}", re.I),
)


def assert_no_obvious_secrets(*values):
    """Reject a few credential shapes before inserting data in SQLite."""
    for value in values:
        if not isinstance(value, str):
            raise TypeError("Expected text input")
        if any(pattern.search(value) for pattern in _PATTERNS):
            raise SensitiveContentError(
                "Potential credential detected; refusing unencrypted storage"
            )
