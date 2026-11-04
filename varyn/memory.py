"""A dependency-free, local-only memory prototype for VARYN.

WARNING: owner_id is supplied by the caller and is NOT authentication.
Never expose this module directly as a public network service.
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from varyn.safety import assert_no_obvious_secrets

class MemoryStore:
    def __init__(self, path, owner_id, *, connection=None):
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("A trusted owner ID is required")
        self.owner_id = owner_id
        self._owns_connection = connection is None
        self.db = sqlite3.connect(path) if connection is None else connection
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY,
            owner_id TEXT NOT NULL,
            project TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        self.db.execute("CREATE INDEX IF NOT EXISTS memories_owner_project ON memories(owner_id,project)")
        self.db.commit()

    def close(self):
        if self._owns_connection:
            self.db.close()

    def add(self, project, content):
        project, content = project.strip(), content.strip()
        if not (1 <= len(project) <= 120 and 1 <= len(content) <= 20000):
            raise ValueError("Invalid project or content length")
        assert_no_obvious_secrets(content)
        with self.db:
            cursor = self.db.execute(
                "INSERT INTO memories(owner_id,project,content,created_at) VALUES(?,?,?,?)",
                (self.owner_id, project, content, datetime.now(timezone.utc).isoformat()))
        return cursor.lastrowid

    def search(self, query, project=None, limit=20):
        if not isinstance(query, str) or not query.strip() or not 1 <= limit <= 100:
            raise ValueError("Invalid query or limit")
        # SQL LIKE wildcard characters in user text must be treated literally.
        literal = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        sql = "SELECT id,project,content,created_at FROM memories WHERE owner_id=? AND content LIKE ? ESCAPE '\\'"
        parameters = [self.owner_id, "%" + literal + "%"]
        if project is not None:
            sql += " AND project=?"
            parameters.append(project)
        sql += " ORDER BY id DESC LIMIT ?"
        parameters.append(limit)
        return [dict(row) for row in self.db.execute(sql, parameters)]

    def delete(self, memory_id, *, project=None):
        """Delete exactly one owner-owned record, optionally scoped to a project.

        Project-scoped deletion is atomic and does not rely on a prior search.
        The owner_id label is not authentication: do not expose this publicly.
        """
        if type(memory_id) is not int or memory_id < 1:
            raise ValueError("Invalid memory identifier")
        if project is not None and (type(project) is not str or
                                    not 1 <= len(project) <= 120):
            raise ValueError("Invalid project")
        sql = "DELETE FROM memories WHERE id=? AND owner_id=?"
        args = [memory_id, self.owner_id]
        if project is not None:
            sql += " AND project=?"
            args.append(project)
        with self.db:
            cursor = self.db.execute(sql, args)
        return cursor.rowcount == 1

def main():
    parser = argparse.ArgumentParser(description="VARYN local memory prototype")
    parser.add_argument("--db", required=True)
    parser.add_argument("--owner", required=True, help="Local label; NOT user authentication")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("--project", required=True)
    add.add_argument("--content", required=True)
    search = sub.add_parser("search")
    search.add_argument("--query", required=True)
    search.add_argument("--project")
    delete = sub.add_parser("delete")
    delete.add_argument("--id", type=int, required=True)
    args = parser.parse_args()
    store = MemoryStore(args.db, args.owner)
    try:
        if args.command == "add":
            result = {"id": store.add(args.project, args.content)}
        elif args.command == "search":
            result = {"items": store.search(args.query, args.project)}
        else:
            result = {"deleted": store.delete(args.id)}
        print(json.dumps(result, ensure_ascii=False))
    finally:
        store.close()

if __name__ == "__main__":
    main()
