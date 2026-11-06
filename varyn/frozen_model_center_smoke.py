"""17S-42: real Tk Model Control Center acceptance in the ACTUAL frozen EXE.

Invoked only from the pre-existing --smoke-only frozen UI path. All content
and offers are fixed fictional fixtures. Never reads API keys, imports user
files, opens external providers or changes the shipping normal-mode GUI.
A CI-scripted approval is NOT a human owner's approval.
"""
import time


class FrozenModelSmokeRejected(RuntimeError):
    """Frozen synthetic Model Control Center failed its fixed no-network gate."""


def synthetic_center_acceptance(owner):
    """Exercise UI quote, refusal, fake response and denied live in one EXE."""
    if (owner is None or getattr(owner, "_closing", True) or
            getattr(owner, "_universal_model_live_capability", True) is not False):
        raise FrozenModelSmokeRejected("Synthetic probe requires offline owner")
    ctrl = getattr(owner, "controller", None)
    if ctrl is None or ctrl.status().get("mode") != "offline_simulation":
        raise FrozenModelSmokeRejected("Legacy provider controller must stay offline")
    center = getattr(owner, "_model_center", None)
    if center is None or not center.winfo_exists():
        raise FrozenModelSmokeRejected("Frozen Model Control Center not available")
    if (center.network.get() is not False or
            center.upstream.get() is not False or center._offers or
            center._running or center._last_receipt is not None):
        raise FrozenModelSmokeRejected("Model center not default OFF/empty")
    initial = center._budget.snapshot()
    if initial["requests_reserved"] != 0:
        raise FrozenModelSmokeRejected("Synthetic probe requires fresh budget")
    if "disabled" not in center.receipt_button.state():
        raise FrozenModelSmokeRejected("Receipt unexpectedly enabled")

    # Invalid/unreviewed UI quote MUST be refused.
    center._add()
    if center._offers or "BLOCKED" not in center.status.get():
        raise FrozenModelSmokeRejected("Unreviewed offer was accepted")

    center.reviewed.set(True)
    center.fixed.set(True)
    center._add()
    if (len(center._offers) != 1 or
            center._offers[0].provider != "fake" or
            center._offers[0].model != "fake-test"):
        raise FrozenModelSmokeRejected("Reviewed synthetic quote failed")
    center._preview()
    if "PREVIEW ONLY" not in center.status.get():
        raise FrozenModelSmokeRejected("Offline price preview failed")
    center._check_readiness()
    if "FAKE only" not in center.status.get():
        raise FrozenModelSmokeRejected("Fake readiness was treated as remote")
    if center._budget.snapshot()["requests_reserved"] != 0:
        raise FrozenModelSmokeRejected("Offline readiness consumed budget")

    # Override the owner-review callback only inside this synthetic-only
    # smoke probe. Never re-use it for real provider requests. A fixed
    # fabricated quote is still NOT verified real pricing.
    original = owner._review_scrollable_manual_text
    reviews = []
    def reject(**kwargs):
        reviews.append(("reject", kwargs))
        return False
    try:
        owner._review_scrollable_manual_text = reject
        center._send()
    finally:
        owner._review_scrollable_manual_text = original
    if (len(reviews) != 1 or "One NEW fake" not in reviews[0][1].get("heading", "")
            or "Request declined" not in center.status.get() or
            center._budget.snapshot()["requests_reserved"] != 0):
        raise FrozenModelSmokeRejected("Denied fake request unexpectedly dispatched")

    def approve_fixed_fake(**kwargs):
        reviews.append(("approve", kwargs))
        if (kwargs.get("heading", "") !=
                "One NEW fake model request, NOT consumer app sync" or
                '"provider": "fake"' not in kwargs.get("content", "") or
                "SYNTHETIC:" not in kwargs.get("content", "") or
                kwargs.get("approve_label") != "Approve ONE exact model request"):
            raise FrozenModelSmokeRejected("Exact fixed fake request review changed")
        return True
    try:
        owner._review_scrollable_manual_text = approve_fixed_fake
        center._send()
    finally:
        owner._review_scrollable_manual_text = original
    if len(reviews) != 2 or reviews[-1][0] != "approve":
        raise FrozenModelSmokeRejected("Fixed fake approval was not reviewed")

    deadline = time.monotonic() + 8
    while center._running and time.monotonic() < deadline:
        owner.update()
        time.sleep(0.015)
    owner.update()
    if (center._running or
            center._budget.snapshot()["requests_reserved"] != 1 or
            not center.answer.get("1.0", "end-1c").startswith("FAKE:") or
            center.network.get() or center.upstream.get() or
            center._last_receipt is not None or
            "disabled" not in center.receipt_button.state() or
            ctrl.status()["requests_used"] != 0):
        raise FrozenModelSmokeRejected("Frozen fake request/consent state invalid")

    # A fictional DEEPSEEK quote is *not* authorization to call the provider.
    # With the smoke-only desktop capability FALSE, even checking the
    # network toggle must not reach an API or open a review dialog.
    center._clear()
    center.provider.set("deepseek")
    center.model.set("synthetic-no-provider-call")
    center.reviewed.set(True)
    center.fixed.set(True)
    center._add()
    if len(center._offers) != 1:
        raise FrozenModelSmokeRejected("Synthetic real-provider quote missing")
    center.network.set(True)
    try:
        owner._review_scrollable_manual_text = lambda **_: (
            _ for _ in ()).throw(FrozenModelSmokeRejected(
                "Offline portable unexpectedly opened live review"))
        center._send()
    finally:
        owner._review_scrollable_manual_text = original
    if (center._running or
            "BLOCKED" not in center.status.get() or
            center._budget.snapshot()["requests_reserved"] != 1):
        raise FrozenModelSmokeRejected("Offline frozen API request was not refused")
    # 17S-43: real frozen Tk new model catalogue must be present but NEVER
    # contact any remote endpoint in smoke-only mode.
    center._open_catalog()
    catalog = center._catalog_window
    if (catalog is None or not catalog.winfo_exists() or
            not center._catalog_lock or catalog.allow_network.get() or
            catalog.authorize_upstream.get() or catalog._attempted or
            catalog.models.size() != 0):
        raise FrozenModelSmokeRejected("Unsafe default model catalogue in frozen EXE")
    catalog.provider.set("deepseek")
    catalog.allow_network.set(True)
    catalog._request_models()
    if (catalog._attempted or catalog._running or
            "BLOCKED" not in catalog.status.get() or
            catalog.models.size() != 0):
        raise FrozenModelSmokeRejected("Frozen offline catalogue GET not denied")
    catalog._dismiss()
    if center._catalog_lock or center._catalog_window is not None:
        raise FrozenModelSmokeRejected("Frozen catalogue did not discard RAM")
    center._dismiss()
    if owner._model_center is not None:
        raise FrozenModelSmokeRejected("Model Center failed to discard RAM data")
    return {
        "format": "varyn.frozen_model_center_synthetic.v1",
        "hosted_real_tk_controls_exercised": True,
        "unreviewed_quote_denied": True,
        "fake_review_rejected": True,
        "one_mock_owner_approved_fake_execution": True,
        "fake_result_in_ram_only": True,
        "provider_receipt_disabled": True,
        "legacy_offline_provider_still_disabled": True,
        "live_model_dispatch_denied": True,
        "model_catalog_default_off": True,
        "model_catalog_network_denied": True,
        "external_provider_requests": 0,
        "operator_personally_approved": False,
        "real_owner_pc_tested": False,
        "actual_provider_api_tested": False,
        "native_consumer_app_sync_tested": False,
    }
