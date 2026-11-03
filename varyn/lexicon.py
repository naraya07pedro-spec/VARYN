"""Tiny, explicit bilingual lexical normalization for the local retrieval prototype.

Not machine translation or semantic search. Keep mappings narrow and auditable:
broad equivalences can accidentally raise false-positive retrieval.
"""
from collections import Counter
import re

_WORDS = re.compile(r"[^\W_]+", re.UNICODE)

# Deliberately small glossary for the first controlled experiment.
# Future mappings must be reviewed against both positive and negative cases.
_CANONICAL = {
    "penyimpanan": "storage",
    "storage": "storage",
    "memori": "memory",
    "memory": "memory",
    "cadangan": "backup",
    "backup": "backup",
}


def canonical_terms(text):
    """Return case-folded term counts with narrow bilingual aliases."""
    if not isinstance(text, str):
        raise TypeError("text must be str")
    return Counter(_CANONICAL.get(term, term)
                   for term in _WORDS.findall(text.casefold()))
