"""Synthetic SQLite index/search microbenchmark, not a laptop guarantee.

Timing uses perf_counter; tracemalloc is Python-only and excludes SQLite's
native allocations and process RSS. No LLM, network, or external dependency.
"""
import argparse
import json
import platform
import sqlite3
import statistics
import tempfile
import time
import tracemalloc
from pathlib import Path

from varyn.context import build_context
from varyn.index import ensure_memory_index
from varyn.memory import MemoryStore


def _timed(operation):
    tracemalloc.start()
    try:
        start = time.perf_counter()
        result = operation()
        elapsed_ms = (time.perf_counter() - start) * 1000
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return result, round(elapsed_ms, 3), peak


def run_benchmark(rows=300, repeats=5):
    """Measure a fresh deterministic synthetic dataset; never assert speed SLAs."""
    if type(rows) is not int or not 20 <= rows <= 5000:
        raise ValueError("rows must be an integer between 20 and 5000")
    if type(repeats) is not int or not 1 <= repeats <= 20:
        raise ValueError("repeats must be an integer between 1 and 20")

    with tempfile.TemporaryDirectory(prefix="varyn-benchmark-") as work:
        db_path = Path(work) / "benchmark.sqlite3"
        store = MemoryStore(db_path, "synthetic-owner")
        try:
            oldest_id = store.add("VARYN", "storage historical anchor")
            for i in range(rows - 1):
                note = (
                    f"storage indexed sample {i:05d} " + "x" * 96
                    if i % 23 == 0
                    else f"unrelated synthetic record {i:05d} " + "x" * 96
                )
                store.add("VARYN", note)

            before_bytes = db_path.stat().st_size
            _, build_ms, build_peak = _timed(lambda: ensure_memory_index(store.db))
            after_bytes = db_path.stat().st_size

            durations, peaks, counts = [], [], []
            for _ in range(repeats):
                context, duration, peak = _timed(
                    lambda: build_context(
                        db_path, "synthetic-owner", "VARYN",
                        "storage", max_chars=4000, max_candidates=100,
                    )
                )
                durations.append(duration)
                peaks.append(peak)
                counts.append(len(context["items"]))

            if not all(count > 0 for count in counts):
                raise AssertionError("Expected indexed matches disappeared")
            anchor = build_context(
                db_path, "synthetic-owner", "VARYN",
                "historical anchor", max_chars=4000, max_candidates=1,
            )
            if not anchor["items"] or anchor["items"][0]["ref"] != f"memory:{oldest_id}":
                raise AssertionError("Historical anchor is not retrievable")

            return {
                "benchmark": "varyn.synthetic.performance.v1",
                "dataset": "deterministic synthetic only",
                "python": platform.python_version(),
                "sqlite_version": sqlite3.sqlite_version,
                "platform": platform.platform(),
                "rows": rows,
                "repeats": repeats,
                "index_build_ms": build_ms,
                "index_build_python_traced_peak_bytes": build_peak,
                "db_main_file_bytes_before_index": before_bytes,
                "db_main_file_bytes_after_index": after_bytes,
                "query_ms_min": min(durations),
                "query_ms_median": round(statistics.median(durations), 3),
                "query_ms_max": max(durations),
                "query_python_traced_peak_bytes_max": max(peaks),
                "returned_items_per_query": counts,
                "historical_anchor_retrieved": True,
                "measurement_limits": (
                    "Python tracemalloc excludes native SQLite memory, process RSS, "
                    "OS page cache and other processes. Main SQLite file size "
                    "excludes journals, WAL and filesystem overhead. CI timing "
                    "does not predict owner-device latency or RAM usage."
                ),
            }
        finally:
            store.close()


def main():
    parser = argparse.ArgumentParser(description="VARYN synthetic performance benchmark")
    parser.add_argument("--rows", type=int, default=300)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(run_benchmark(args.rows, args.repeats), indent=2))


if __name__ == "__main__":
    main()
