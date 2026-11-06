"""Declarative discovery of VARYN integrations, skills, and plugins.

Catalog entries are NOT connected or executable. No ChatGPT tokens are imported.
Read-only stdlib module with strict static JSON schema and path restrictions.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

_ID = re.compile(r"\A[a-z][a-z0-9_-]{0,63}\Z")
_ALLOWED = frozenset(("connector", "plugin_candidate", "skill_candidate"))
_MAX_CATALOG_BYTES = 65536


class CatalogRejected(ValueError):
    pass


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    name: str
    kind: str
    status: str = "catalog_only"

    @property
    def available(self) -> bool:
        # This module is never evidence of a live session or runnable adapter.
        return False


def load_catalog(path=None) -> tuple[CatalogEntry, ...]:
    if path is None:
        path = Path(__file__).resolve().parent.parent / "integrations" / "catalog.json"
    path = Path(path)
    if not path.is_file() or path.stat().st_size > _MAX_CATALOG_BYTES:
        raise CatalogRejected("Missing or excessive catalog file")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        raise CatalogRejected("Invalid JSON catalog") from None
    if type(raw) is not dict or raw.get("schema") != "varyn.integration_catalog.v1":
        raise CatalogRejected("Unsupported catalog schema")
    result = []
    names = set()
    for key, kind in (("connectors", "connector"),
                      ("plugins", "plugin_candidate"),
                      ("skills", "skill_candidate")):
        items = raw.get(key)
        if type(items) is not list or len(items) > 128:
            raise CatalogRejected("Invalid category list")
        for value in items:
            if (type(value) is not dict or
                    value.get("kind") != kind or
                    type(value.get("id")) is not str or
                    not _ID.fullmatch(value["id"]) or
                    type(value.get("name")) is not str or
                    not 1 <= len(value["name"]) <= 90 or
                    value.get("status") != "catalog_only"):
                raise CatalogRejected("Invalid catalog entry")
            entry = CatalogEntry(value["id"], value["name"], kind)
            identifier = (kind, entry.id)
            if identifier in names:
                raise CatalogRejected("Duplicate catalog item")
            names.add(identifier)
            result.append(entry)
    return tuple(result)


def display_catalog() -> str:
    entries = load_catalog()
    return json.dumps({
        "schema": "varyn.catalog_summary.v1",
        "connectors": [e.name for e in entries if e.kind == "connector"],
        "plugins": [e.name for e in entries if e.kind == "plugin_candidate"],
        "skills": [e.name for e in entries if e.kind == "skill_candidate"],
        "connected_accounts": 0,
        "runnable_external_integrations": 0,
        "inherited_chatgpt_sessions": False,
    }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print(display_catalog())
