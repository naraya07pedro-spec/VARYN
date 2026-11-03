"""Reproducible, synthetic retrieval evaluation for VARYN.

This is a small regression benchmark, not real-world retrieval accuracy.
No model, network, user data, or paid API is used.
"""
import argparse
import json
import tempfile
from pathlib import Path

from varyn.context import build_context
from varyn.decisions import DecisionJournal
from varyn.memory import MemoryStore


def _scenario(name, setup, query, expected, max_chars=4000, max_candidates=500):
    """Execute one independently isolated, pre-labeled synthetic scenario."""
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "eval.sqlite3"
        memory = MemoryStore(path, "fixture-owner")
        journal = DecisionJournal(path, "fixture-owner")
        try:
            setup(memory, journal)
        finally:
            journal.close()
            memory.close()
        result = build_context(
            path, "fixture-owner", "VARYN", query,
            max_chars=max_chars, max_candidates=max_candidates,
        )
        returned = [
            item["key"] if item["type"] == "decision"
            else item["content"] for item in result["items"]
        ]
        # Expected strings are exact keys or contents. No automatic ground-truth
        # labeling: this benchmark intentionally specifies relevance in advance.
        success = expected in returned if expected is not None else not returned
        rank = returned.index(expected) + 1 if expected in returned else None
        return {
            "case": name,
            "expected": expected,
            "returned": returned,
            "status": result["status"],
            "hit": success,
            "reciprocal_rank": 1.0 / rank if rank is not None else 0.0,
        }


def run_evaluation():
    """Report all cases, including known limitations that remain after alias expansion."""
    cases = [
        _scenario(
            "literal_memory",
            lambda m, d: m.add("VARYN", "storage location is D drive"),
            "storage drive", "storage location is D drive",
        ),
        _scenario(
            "latest_revision",
            lambda m, d: (
                d.put("VARYN", "storage", "old storage location C", "test:old"),
                d.put("VARYN", "storage", "new storage location D", "test:new", 1),
            ),
            "storage location", "storage",
        ),
        _scenario(
            "other_project_excluded",
            lambda m, d: m.add("RepoPilot", "storage location is X"),
            "storage", None,
        ),
        _scenario(
            "bilingual_storage_alias",
            lambda m, d: m.add("VARYN", "storage location is D drive"),
            "penyimpanan", "storage location is D drive",
        ),
        _scenario(
            "historical_index_hit",
            lambda m, d: (
                m.add("VARYN", "storage original relevant"),
                m.add("VARYN", "irrelevant newer"),
            ),
            "storage", "storage original relevant",
            max_candidates=1,
        ),
        _scenario(
            "over_budget",
            lambda m, d: m.add("VARYN", "storage " + "Q" * 5000),
            "storage", "storage " + "Q" * 5000,
            max_chars=350,
        ),
    ]
    positives = [c for c in cases if c["expected"] is not None]
    negatives = [c for c in cases if c["expected"] is None]
    return {
        "benchmark": "varyn.synthetic.retrieval.v1",
        "dataset_type": "hand_labeled_synthetic_only",
        "cases": cases,
        "metrics": {
            "positive_hit_rate": sum(c["hit"] for c in positives) / len(positives),
            "positive_mrr": sum(c["reciprocal_rank"] for c in positives) / len(positives),
            "negative_correct_rejection_rate": (
                sum(c["hit"] for c in negatives) / len(negatives)
            ),
            "positive_cases": len(positives),
            "negative_cases": len(negatives),
        },
        "limitations": (
            "Small purpose-built fixtures, not representative user queries. "
            "A tiny glossary handles selected aliases but misses unlisted synonyms and over-budget evidence. Indexed matching now finds historical records outside the recent-write pool. "
            "Owner labels are not authentication; no private data or real LLM calls."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="VARYN synthetic retrieval evaluation")
    parser.parse_args()
    print(json.dumps(run_evaluation(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
