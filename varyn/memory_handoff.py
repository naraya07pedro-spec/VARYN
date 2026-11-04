"""17N explicit, bounded local note selection for collaboration.

Selection is always restricted to the current local owner label and project.
No provider calls, transcript capture, or automatic memory retrieval.
"""
from varyn.desktop_memory import DesktopMemory
from varyn.providers import _validate


def parse_note_ids(raw):
    if type(raw) is not str or len(raw) > 32:
        raise ValueError("Expected comma-separated note IDs")
    parts = [p.strip() for p in raw.split(",")]
    if not 1 <= len(parts) <= 3 or any(
        not p.isascii() or not p.isdecimal() or len(p) > 10 for p in parts
    ):
        raise ValueError("Use 1..3 positive numeric IDs")
    ids = tuple(int(p) for p in parts)
    if any(i < 1 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("IDs must be positive and unique")
    return ids


def selected_memory_context(memory, project, ids):
    if type(memory) is not DesktopMemory:
        raise ValueError("Opt-in desktop memory required")
    memory._ensure()
    project = memory._project(project)
    if (type(ids) not in (tuple, list) or not 1 <= len(ids) <= 3 or
        any(type(i) is not int or i < 1 for i in ids) or
        len(set(ids)) != len(ids)):
        raise ValueError("Select 1..3 unique positive note IDs")
    # Bound by owner + exact project. Never silently omit missing IDs.
    rows = []
    for note_id in ids:
        record = memory._store.db.execute(
            "SELECT id, content, created_at FROM memories "
            "WHERE owner_id=? AND project=? AND id=?",
            (memory._store.owner_id, project, note_id),
        ).fetchone()
        if record is None:
            raise PermissionError("Note missing or outside selected project")
        content = memory._note(record["content"])
        rows.append({
            "type": "memory",
            "ref": "memory:" + str(note_id),
            "project": project,
            "content": content,
            "created_at": record["created_at"],
            "untrusted": True,
            "source_verified": False,
        })
    context = {
        "format": "varyn.context.v1",
        "project": project,
        "retrieval": "explicit_note_ids",
        "owner_label_not_authenticated": True,
        "items": rows,
    }
    _validate("fake-test", "preflight", 16, 10, context)
    return context
