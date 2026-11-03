"""Local-only VARYN preflight: Python, Tkinter and process RSS.

Never reads API keys, network, personal files, or external provider config.
Tk GUI creation is optional and must only run from a user desktop session.
"""
import argparse
import ctypes
import json
import os
import platform
import sys
from pathlib import Path


def _windows_rss():
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = (
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD
    )
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    if not psapi.GetProcessMemoryInfo(
        kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    ):
        return None
    return int(counters.WorkingSetSize)


def process_rss_bytes():
    """Best-effort resident memory for THIS Python doctor process, not VARYN GUI."""
    try:
        if os.name == "nt":
            return _windows_rss()
        status = Path("/proc/self/status")
        if sys.platform.startswith("linux") and status.is_file():
            for line in status.read_text(encoding="ascii").splitlines():
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) == 3 and parts[2] == "kB":
                        return int(parts[1]) * 1024
    except (OSError, ValueError, AttributeError):
        return None
    return None


def run_preflight(*, gui_smoke=False):
    result = {
        "format": "varyn.desktop_doctor.v1",
        "python_version": platform.python_version(),
        "python_supported": sys.version_info >= (3, 10),
        "platform": platform.system().lower(),
        "tkinter_import": False,
        "tk_version": None,
        "doctor_process_rss_bytes": process_rss_bytes(),
        "rss_scope": "doctor_process_only",
        "network_calls": 0,
        "live_provider_enabled": False,
        "gui_smoke": "not_requested",
    }
    try:
        import tkinter as tk
        result["tkinter_import"] = True
        result["tk_version"] = str(tk.TkVersion)
    except ImportError:
        result["gui_smoke"] = "tkinter_unavailable" if gui_smoke else "not_requested"
        return result

    if gui_smoke:
        try:
            from varyn.desktop import VarynDesktop
            from varyn.desktop_controller import DesktopController
            window = VarynDesktop(controller=DesktopController())
            try:
                window.update_idletasks()
                window.update()
                result["gui_smoke"] = "passed"
            finally:
                window.destroy()
        except tk.TclError:
            result["gui_smoke"] = "no_graphical_display"
        except Exception:
            result["gui_smoke"] = "failed"
    return result


def main():
    parser = argparse.ArgumentParser(description="Offline desktop preflight")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--gui-smoke", action="store_true",
                        help="Create and close actual GUI on THIS desktop")
    args = parser.parse_args()
    data = run_preflight(gui_smoke=args.gui_smoke)
    if args.json:
        print(json.dumps(data, sort_keys=True))
    else:
        for key, value in data.items():
            print(f"{key}: {value}")
    return 0 if data["python_supported"] and data["tkinter_import"] and (
        not args.gui_smoke or data["gui_smoke"] == "passed"
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
