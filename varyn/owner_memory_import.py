"""Local import of user-selected ChatGPT exports into a Windows DPAPI vault.

No account session access, hidden file scanning, HTTP uploads or automatic model
context injection. Export contents are UNTRUSTED and must be reviewed by owner.
This is a bounded, explicitly selected archive importer, not live sync.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import uuid
import zipfile

from varyn.dpapi_vault import read_sealed, write_sealed, SealedDataError

SCHEMA = "varyn.owner_imported_memory.v1"
MAX_EXPORT = 64 * 1024 * 1024
MAX_JSON = 48 * 1024 * 1024
MAX_VAULT = 800 * 1024
MAX_SOURCES = 300
MAX_TURNS = 90
MAX_TEXT = 6500


class MemoryImportRejected(ValueError):
    pass


def vault_path():
    root = Path(os.environ.get("LOCALAPPDATA") or
                (Path.home() / "AppData" / "Local")) / "VARYN"
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise MemoryImportRejected("Memory directory must not be a symlink")
    return root / "imported-memory.varyn"


def _bounded_json(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_EXPORT:
        raise MemoryImportRejected("Export file missing or exceeds local safety limit")
    if p.suffix.casefold() == ".json":
        if p.stat().st_size > MAX_JSON:
            raise MemoryImportRejected("JSON export too large")
        content = p.read_bytes()
    elif p.suffix.casefold() == ".zip":
        try:
            with zipfile.ZipFile(p) as archive:
                matches = [entry for entry in archive.infolist()
                           if entry.filename == "conversations.json" and not entry.is_dir()]
                if len(matches) != 1 or matches[0].file_size > MAX_JSON:
                    raise MemoryImportRejected("ChatGPT conversations.json missing or too large")
                with archive.open(matches[0]) as stream:
                    content = stream.read(MAX_JSON + 1)
        except (zipfile.BadZipFile, RuntimeError, EOFError, OSError):
            raise MemoryImportRejected("Invalid ZIP export") from None
    else:
        raise MemoryImportRejected("Choose a ChatGPT .zip or conversations.json")
    if len(content) > MAX_JSON:
        raise MemoryImportRejected("Export contents exceed safety limit")
    try:
        obj = json.loads(content)
    except (UnicodeError, ValueError, RecursionError):
        raise MemoryImportRejected("Invalid exported JSON") from None
    if type(obj) is not list:
        raise MemoryImportRejected("Unrecognized ChatGPT conversations format")
    return obj


def parse_chatgpt_export(path):
    """Parse owner-selected export into short *candidate* records only.

    Does not save or transmit. Caller must explicitly choose rows to import.
    """
    raw = _bounded_json(path)
    results = []
    for item in raw[:5000]:
        if type(item) is not dict or type(item.get("mapping")) is not dict:
            continue
        title = item.get("title")
        if type(title) is not str:
            title = "Untitled"
        title = " ".join(title.split())[:120] or "Untitled"
        mapping = item["mapping"]
        messages = []
        for node in list(mapping.values())[:4000]:
            if type(node) is not dict:
                continue
            data = node.get("message")
            if type(data) is not dict:
                continue
            author = data.get("author")
            role = author.get("role") if type(author) is dict else None
            if role not in ("user", "assistant"):
                continue
            body = data.get("content")
            parts = body.get("parts") if type(body) is dict else None
            if type(parts) is not list:
                continue
            txt = " ".join(x for x in parts if type(x) is str)
            txt = " ".join(txt.split())
            if not txt:
                continue
            messages.append((data.get("create_time") or 0, role, txt[:1600]))
        messages.sort(key=lambda row: (type(row[0]) not in (int,float), 
                                       float(row[0]) if type(row[0]) in (int,float) else 0))
        tail = messages[-MAX_TURNS:]
        rendered = "\n".join(role + ": " + text for _, role, text in tail)
        if not rendered:
            continue
        ident = item.get("id")
        if type(ident) is not str:
            ident = title + rendered[:100]
        source = hashlib.sha256(("chatgpt:" + ident).encode("utf-8")).hexdigest()
        results.append({
            "source": source,
            "title": title,
            "content": rendered[:MAX_TEXT],
            "origin": "chatgpt_user_export",
        })
        if len(results) >= 2000:
            break
    return results


def _validate_records(records):
    if type(records) is not list or len(records) > MAX_SOURCES:
        raise MemoryImportRejected("Invalid memory record count")
    seen = set()
    for obj in records:
        if (type(obj) is not dict or set(obj) !=
                {"source", "title", "content", "origin"} or
                type(obj["source"]) is not str or
                len(obj["source"]) != 64 or
                any(x not in "0123456789abcdef" for x in obj["source"]) or
                obj["source"] in seen or
                obj["origin"] != "chatgpt_user_export" or
                type(obj["title"]) is not str or len(obj["title"]) > 120 or
                type(obj["content"]) is not str or len(obj["content"]) > MAX_TEXT):
            raise MemoryImportRejected("Invalid encrypted memory schema")
        seen.add(obj["source"])


def load_vault(path=None):
    path = Path(path) if path is not None else vault_path()
    if not path.exists():
        return []
    if path.is_symlink():
        raise MemoryImportRejected("Symlink vault refused")
    try:
        payload = json.loads(read_sealed(path))
    except (ValueError, UnicodeError, SealedDataError, OSError):
        raise MemoryImportRejected("Encrypted memory vault unavailable") from None
    if type(payload) is not dict or payload.get("schema") != SCHEMA:
        raise MemoryImportRejected("Unknown encrypted memory format")
    rows = payload.get("records")
    _validate_records(rows)
    return rows


def import_selected(candidates, selected_sources, *, path=None):
    """Explicit selected records; encrypt before disk, atomic snapshot replace."""
    path = Path(path) if path is not None else vault_path()
    if path.is_symlink() or not path.parent.is_dir() or path.parent.is_symlink():
        raise MemoryImportRejected("Invalid memory destination")
    if type(selected_sources) not in (list,tuple,set) or not selected_sources:
        raise MemoryImportRejected("Select conversations to import first")
    requested = set(selected_sources)
    if any(type(x) is not str for x in requested) or len(requested)>MAX_SOURCES:
        raise MemoryImportRejected("Invalid selection")
    before = load_vault(path)
    merged = {r["source"]: r for r in before}
    added = 0
    for record in candidates:
        if type(record) is not dict or record.get("source") not in requested:
            continue
        _validate_records([record])
        if record["source"] not in merged:
            merged[record["source"]] = record
            added += 1
    if len(merged) > MAX_SOURCES:
        raise MemoryImportRejected("Memory vault is full; select fewer conversations")
    selected_found = {r["source"] for r in candidates
                      if type(r) is dict and r.get("source") in requested}
    if selected_found != requested:
        raise MemoryImportRejected("Selection did not match preview")
    result = list(merged.values())
    data = json.dumps({"schema":SCHEMA, "records":result},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_VAULT:
        raise MemoryImportRejected("Encrypted memory capacity reached")
    if added == 0:
        return {"added":0, "total":len(result)}
    provisional = path.parent / (".memory-" + uuid.uuid4().hex + ".varyn")
    try:
        write_sealed(provisional, data)
        if read_sealed(provisional) != data:
            raise MemoryImportRejected("Encrypted memory verification failed")
        os.replace(provisional, path)
    except (OSError, ValueError, SealedDataError):
        raise MemoryImportRejected("Could not securely save imported memory") from None
    finally:
        try:
            provisional.unlink(missing_ok=True)
        except OSError:
            pass
    return {"added":added, "total":len(result)}


def search_memory(query, *, path=None, limit=10):
    if type(query) is not str or not 1 <= len(query.strip()) <= 200:
        raise MemoryImportRejected("Enter a search query")
    if type(limit) is not int or not 1 <= limit <= 30:
        raise MemoryImportRejected("Invalid search limit")
    terms = [term.casefold() for term in query.split()[:12]]
    matches = []
    for row in load_vault(path):
        combined = (row["title"] + " " + row["content"]).casefold()
        score = sum(combined.count(t) for t in terms if len(t) >= 2)
        if score:
            matches.append((score, row))
    matches.sort(key=lambda x:x[0],reverse=True)
    return [row for _,row in matches[:limit]]
