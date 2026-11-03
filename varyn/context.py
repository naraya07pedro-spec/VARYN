"""Deterministic, bounded context selection for the VARYN local prototype.

Not semantic retrieval, not a security boundary, and not an LLM prompt.
All returned memory text is untrusted user content.
"""
import argparse
import json
import re
from collections import Counter

from varyn.decisions import DecisionJournal
from varyn.memory import MemoryStore

_WORDS = re.compile(r"[^\W_]+", re.UNICODE)


def _terms(text):
    return Counter(_WORDS.findall(text.casefold()))


def _relevance(query_terms, text):
    terms = _terms(text)
    return sum(min(terms[word], 3) * count for word, count in query_terms.items())


def _encode(document):
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_context(db_path, owner_id, project, query, max_chars=4000, max_candidates=500):
    """Return a JSON-compatible package no longer than max_chars when encoded.

    Only records for the caller-specified owner label and project are considered.
    Decision history is reduced to its latest revision per key; raw memories are
    selected from the latest max_candidates rows, ranked by lexical overlap.
    A zero-overlap record is not included.
    """
    if not isinstance(project, str) or not 1 <= len(project.strip()) <= 120:
        raise ValueError("Invalid project")
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("Invalid query")
    if type(max_chars) is not int or not 300 <= max_chars <= 100000:
        raise ValueError("max_chars must be between 300 and 100000")
    if type(max_candidates) is not int or not 1 <= max_candidates <= 5000:
        raise ValueError("max_candidates must be between 1 and 5000")
    project = project.strip()
    query_terms = _terms(query)
    if not query_terms:
        raise ValueError("Query must contain words")

    # This package contains data only. A later provider adapter must treat every
    # content field as untrusted data, never as instructions from the user/system.
    result = {
        "format": "varyn.context.v1",
        "owner_label_not_authenticated": True,
        "project": project,
        "query": query,
        "retrieval": "lexical_overlap_recent_pool",
        "items": [],
        "status": "matches_exceeded_budget",
        "duplicates_skipped": 0,
    }
    if len(_encode(result)) > max_chars:
        raise ValueError("Budget too small even for context metadata")

    memories = MemoryStore(db_path, owner_id)
    journal = DecisionJournal(db_path, owner_id)
    try:
        memory_rows = memories.db.execute(
            """SELECT id, content, created_at FROM memories
            WHERE owner_id=? AND project=? ORDER BY id DESC LIMIT ?""",
            (memories.owner_id, project, max_candidates),
        ).fetchall()
        decision_rows = journal.db.execute(
            """SELECT d.decision_key,d.revision,d.content,d.source_ref,d.created_at
            FROM decision_revisions d
            WHERE d.owner_id=? AND d.project=? AND d.revision=(
              SELECT MAX(r.revision) FROM decision_revisions r
              WHERE r.owner_id=d.owner_id AND r.project=d.project
                AND r.decision_key=d.decision_key
            ) ORDER BY d.id DESC LIMIT ?""",
            (journal.owner_id, project, max_candidates),
        ).fetchall()

        scored = []
        for row in memory_rows:
            overlap = _relevance(query_terms, row["content"])
            if overlap:
                scored.append((overlap, 0, row["id"], {
                    "type": "memory", "ref": f'memory:{row["id"]}',
                    "content": row["content"], "created_at": row["created_at"],
                }))
        for row in decision_rows:
            overlap = _relevance(query_terms, row["decision_key"] + " " + row["content"])
            if overlap:
                scored.append((overlap, 1, row["revision"], {
                    "type": "decision", "key": row["decision_key"],
                    "revision": row["revision"], "source_ref": row["source_ref"],
                    "source_verified": False,
                    "content": row["content"], "created_at": row["created_at"],
                }))
        # Highest lexical score first; equal scores favor decisions, then newest ID.
        scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        seen_memory_text = set()
        decision_text = {
            " ".join(entry[3]["content"].casefold().split())
            for entry in scored if entry[3]["type"] == "decision"
        }
        for _, _, _, item in scored:
            # Only exact case/whitespace-normalized repeats are merged. Different
            # decision keys remain separate even if their wording is identical.
            if item["type"] == "memory":
                normalized = " ".join(item["content"].casefold().split())
                if normalized in seen_memory_text or normalized in decision_text:
                    result["duplicates_skipped"] += 1
                    continue
                seen_memory_text.add(normalized)
            result["items"].append(item)
            if len(_encode(result)) > max_chars:
                result["items"].pop()
        # Status distinguishes no lexical match from evidence that simply cannot
        # fit in the requested character budget. Neither means "no facts exist".
        result["status"] = (
            "matched" if result["items"] else
            "matches_exceeded_budget" if scored else "no_match_in_sample"
        )
        # Diagnostics themselves take space. Fail closed rather than exceeding
        # the requested serialized-document budget.
        if len(_encode(result)) > max_chars:
            raise ValueError("Budget too small for retrieval diagnostics")
        return result
    finally:
        journal.close()
        memories.close()


def main():
    parser = argparse.ArgumentParser(description="Build bounded local VARYN context JSON")
    parser.add_argument("--db", required=True)
    parser.add_argument("--owner", required=True, help="Not authentication")
    parser.add_argument("--project", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--max-chars", type=int, default=4000)
    args = parser.parse_args()
    context = build_context(args.db, args.owner, args.project, args.query, args.max_chars)
    print(_encode(context))


if __name__ == "__main__":
    main()
