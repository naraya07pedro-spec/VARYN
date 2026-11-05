"""17S-29 Windows portable desktop entry, independent of installed Python.

Experimental manual official-app workbench. Shipped GUI is offline for model
API providers; NO automatic consumer app history access, private-file grants,
network sync, or background service is activated by this entry point.

Portable --smoke-only is a no-action GUI construction/teardown probe, NOT
owner acceptance or remote app connectivity.
"""
import argparse
import ctypes
import os
import tkinter as tk
from tkinter import messagebox

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


def windows_non_admin():
    """Fail closed if Windows elevation status is unknown."""
    if os.name != "nt":
        return False
    try:
        return not bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError, ValueError):
        return False


def create_portable_desktop(*, smoke_only=False):
    """Construct real Tk offline-model desktop; no provider session login."""
    if type(smoke_only) is not bool:
        raise ValueError("Invalid smoke-only flag")
    controller = DesktopController(allow_live_providers=False)
    window = VarynDesktop(controller=controller)
    window.title("VARYN | Portable manual official-app workbench (EXPERIMENTAL)")
    if smoke_only:
        # CI uses actual Tk creation, a workbench widget, and close on
        # Windows hosted runner; never calls browser, clipboard or AI APIs.
        window.withdraw()
        window._open_relay_workbench()
        if (window._relay_workbench is None or
                not window._relay_workbench.winfo_exists() or
                controller.status()["mode"] != "offline_simulation"):
            window._close()
            raise RuntimeError("Offline workbench self-check failed")
        window.update_idletasks()
        window._close()
        return None
    # Real user sees the focused workbench without needing to discover the
    # long legacy desktop control list. The main UI remains available.
    window.after_idle(window._open_relay_workbench)
    return window


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Windows portable VARYN, experimental manual official-app GUI")
    parser.add_argument("--smoke-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.smoke_only and not windows_non_admin():
        try:
            messagebox.showerror(
                "VARYN | Normal user required",
                "Run VARYN-Portable.exe as a normal non-administrator Windows "
                "user. This app never needs elevation.",
            )
        except tk.TclError:
            pass
        return 2
    if os.name != "nt":
        return 2
    try:
        window = create_portable_desktop(smoke_only=args.smoke_only)
        if window is not None:
            window.mainloop()
    except tk.TclError:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
