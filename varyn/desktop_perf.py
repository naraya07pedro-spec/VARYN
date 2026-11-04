"""Synthetic desktop controller memory probe; not whole-process RSS or UI usage.

Run: python -m varyn.desktop_perf
Only FakeProvider is used. Peak tracemalloc tracks Python allocations, not
native Tk rendering, process RSS, or Windows laptop responsiveness.
"""
import json
import tracemalloc
from varyn.desktop_controller import DesktopController


def probe(requests=10, message_chars=120):
    if type(requests) is not int or not 1 <= requests <= 10:
        raise ValueError("Requests must be 1..10")
    if type(message_chars) is not int or not 1 <= message_chars <= 4000:
        raise ValueError("Message length must be 1..4000")
    tracemalloc.start()
    try:
        desktop = DesktopController(
            max_requests=requests,
            max_reserved_output_tokens=requests * 256,
        )
        for _ in range(requests):
            desktop.send("x" * message_chars, max_output_tokens=256)
        current, peak = tracemalloc.get_traced_memory()
        return {
            "format": "varyn.desktop_memory_probe.v1",
            "fake_requests": requests,
            "message_chars": message_chars,
            "tracemalloc_current_bytes": current,
            "tracemalloc_peak_bytes": peak,
            "includes_native_tk_or_process_rss": False,
            "device_ram_acceptance": False,
            "network_used": False,
        }
    finally:
        tracemalloc.stop()


def main():
    print(json.dumps(probe(), sort_keys=True))


if __name__ == "__main__":
    main()
