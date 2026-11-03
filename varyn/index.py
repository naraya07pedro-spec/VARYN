"""SQLite FTS5 index for VARYN memory notes, including legacy backfill.

SQLite's index lives on disk, not in a Python list. It is not an
authorization layer or a complete semantic search solution.
"""
from varyn.lexicon import canonical_terms, _CANONICAL


def ensure_memory_index(connection):
    """Initialize FTS5 and triggers, rebuilding once for pre-existing notes.

    An unavailable FTS5 extension is a visible error, not a silent fallback
    to a potentially misleading recency-only search.
    """
    present = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_fts'"
    ).fetchone()
    with connection:
        connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts "
            "USING fts5(content, content='memories', content_rowid='id')"
        )
        connection.execute("""CREATE TRIGGER IF NOT EXISTS memory_fts_insert
            AFTER INSERT ON memories BEGIN
                INSERT INTO memory_fts(rowid, content)
                VALUES (new.id, new.content);
            END""")
        connection.execute("""CREATE TRIGGER IF NOT EXISTS memory_fts_delete
            AFTER DELETE ON memories BEGIN
                INSERT INTO memory_fts(memory_fts, rowid, content)
                VALUES ('delete', old.id, old.content);
            END""")
        connection.execute("""CREATE TRIGGER IF NOT EXISTS memory_fts_update
            AFTER UPDATE OF content ON memories BEGIN
                INSERT INTO memory_fts(memory_fts, rowid, content)
                VALUES ('delete', old.id, old.content);
                INSERT INTO memory_fts(rowid, content)
                VALUES (new.id, new.content);
            END""")
        if not present:
            # Populate from an existing DB on first use. Subsequent changes
            # are tracked by triggers. Large migrations are NOT benchmarked yet.
            connection.execute("INSERT INTO memory_fts(memory_fts) VALUES ('rebuild')")


def match_expression(query, max_terms=24):
    """Build an escaped FTS5 OR query with explicit bilingual aliases.

    Every lexical atom is quoted and the whole MATCH expression is a bound
    parameter, rather than interpolated SQL.
    """
    canonical = canonical_terms(query)
    if not canonical:
        raise ValueError("Query contains no indexable words")
    groups = []
    for term in list(canonical)[:max_terms]:
        variants = {term}
        variants.update(
            surface for surface, target in _CANONICAL.items() if target == term
        )
        phrases = ['"' + variant.replace('"', '""') + '"' for variant in sorted(variants)]
        groups.append("(" + " OR ".join(phrases) + ")")
    return " OR ".join(groups)


def retrieve_indexed_memories(connection, owner_id, project, query, limit):
    """Return matching indexed notes, newest-first, scoped before LIMIT."""
    ensure_memory_index(connection)
    return connection.execute(
        """SELECT m.id, m.content, m.created_at FROM memory_fts
           JOIN memories AS m ON m.id = memory_fts.rowid
           WHERE memory_fts MATCH ? AND m.owner_id=? AND m.project=?
           ORDER BY m.id DESC LIMIT ?""",
        (match_expression(query), owner_id, project, limit),
    ).fetchall()
