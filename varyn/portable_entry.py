"""17S-29 Windows portable desktop entry, independent of installed Python.

Experimental manual official-app workbench. The legacy model controller is
OFFLINE in Portable, while the new Model Control Center permits owner-reviewed
pinned API calls only in normal non-smoke mode, after an independent network
toggle and OS environment credential. Neither mode auto-reads consumer app
history/memory, private files or browser session secrets.

Portable --smoke-only is a no-action GUI construction/teardown probe, NOT
owner acceptance or remote app connectivity.
"""
import argparse
import ctypes
import os
import tkinter as tk
from tkinter import messagebox

from varyn.desktop import VarynDesktop
from varyn.consumer_workspace import ConsumerWorkspace
from varyn.desktop_controller import DesktopController
from varyn.frozen_draft_probe import run_probe_phase, FrozenProbeRejected
from varyn.dpapi_vault import SealedDataError, UnsupportedPlatformError
from varyn.frozen_model_center_smoke import synthetic_center_acceptance


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
    window = VarynDesktop(
        controller=controller,
        # Only the new gateway may opt in to live endpoints per request.
        # The pre-existing portable provider controller REMAINS offline.
        allow_universal_model_network=not smoke_only,
    )
    window.title("VARYN | Local AI, Tasks & Integrations (EXPERIMENTAL)")
    if smoke_only:
        # CI uses actual Tk creation, a workbench widget, and close on
        # Windows hosted runner; never calls browser, clipboard or AI APIs.
        window.withdraw()
        window._open_relay_workbench()
        window._open_model_control_center()
        center = window._model_center
        if (center is None or not center.winfo_exists() or
                center.network.get() is not False or
                center._offers != [] or
                window._universal_model_live_capability or
                window._relay_workbench is None or
                not window._relay_workbench.winfo_exists() or
                controller.status()["mode"] != "offline_simulation"):
            window._close()
            raise RuntimeError("Offline workbench self-check failed")
        # 17S-42: real frozen EXE tests the actual Tk fake-request,
        # review-denial, no-network API guard and memory cleanup, not just
        # construction of widgets. Only fixed fictional data is permitted.
        try:
            synthetic_center_acceptance(window)
        finally:
            window._close()
        return None
    # This Tk root runs internal controllers; it must never appear as a second window.
    window.withdraw()
    # The local task database is never created in smoke-only mode.
    def open_home():
        try:
            window._owner_home = ConsumerWorkspace(window)
            window._owner_home._close_root_on_exit = True
        except (OSError, ValueError):
            # A corrupt or inaccessible task DB must not prevent the owner from
            # using the existing, separately approved model controls.
            # Do not reopen the obsolete technical controller on startup error.
            messagebox.showerror(
                "VARYN | Startup error",
                "Could not open the workspace. Check local task database permissions.",
            )
            window._close()
    window.after_idle(open_home)
    return window


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Windows portable VARYN, experimental manual official-app GUI")
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--synthetic-draft-smoke", choices=("write", "read"))
    parser.add_argument("--smoke-directory")
    args = parser.parse_args(argv)
    if args.synthetic_draft_smoke is not None:
        # Restricted test-only subprocess. No Tk, browser, clipboard or provider.
        if args.smoke_only or not args.smoke_directory:
            return 2
        try:
            return run_probe_phase(args.synthetic_draft_smoke, args.smoke_directory)
        except (FrozenProbeRejected, SealedDataError,
                UnsupportedPlatformError, FileExistsError, OSError, ValueError):
            return 4
    if args.smoke_directory is not None:
        return 2
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
