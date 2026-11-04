"""Checkpoint 14B: consent-oriented desktop bridge to synthetic agent actions.

This is NOT identity-authenticated human approval. Only the trusted Tk callback
should call decide(), never the model's text. No external actions or persistence.
"""
from dataclasses import dataclass

from varyn.agent_runtime import BoundedAgent, AgentRejected


@dataclass(frozen=True)
class ApprovalPreview:
    proposal_id: str
    tool: str
    digest: str
    risk: str
    summary: str
    mutates: bool


class DesktopApprovalController:
    """Keeps model-untrusted proposal distinct from UI consent decision."""

    def __init__(self, agent=None, *, journal=None):
        self.agent = agent if agent is not None else BoundedAgent(max_steps=8)
        self.journal = journal
        # Restart never restores executable proposals or approval tokens.
        self.recovered = journal.recover() if journal is not None else None
        self._waiting = {}

    def propose(self, tool, arguments):
        proposal = self.agent.propose(tool, arguments)
        if tool == "stage_note":
            # Show exactly what would be stored, with a visible 200-char bound.
            summary = "Store temporary synthetic note in RAM: " + proposal.arguments["text"]
            risk = "Changes in-memory demo state only; no files or network"
        elif tool == "inspect_status":
            summary = "Read synthetic agent status counters"
            risk = "Read-only; no files or network"
        else:
            raise AgentRejected("Unregistered tool")
        preview = ApprovalPreview(proposal.proposal_id, proposal.tool,
                                  proposal.digest, risk, summary, proposal.mutates)
        if self.journal is not None:
            try:
                self.journal.record_proposal(
                    preview.proposal_id, preview.tool, preview.digest
                )
            except Exception:
                self.agent.reject(preview.proposal_id)
                raise
        self._waiting[proposal.proposal_id] = preview
        return preview

    def decide(self, proposal_id, displayed_digest, *, approved):
        """Bind UI decision to an exact preview before issuing any token."""
        if type(approved) is not bool:
            raise ValueError("Approval decision must be boolean")
        if not isinstance(displayed_digest, str):
            raise AgentRejected("Invalid displayed proposal digest")
        preview = self._waiting.get(proposal_id)
        if preview is None or preview.digest != displayed_digest:
            raise AgentRejected("Proposal preview mismatch or already resolved")
        # Remove from UI waiting list before dispatch to prevent duplicate clicks.
        if not approved:
            # A crash between runtime reject and journal commit remains pending,
            # which recovery will flag for fresh manual review, never replay.
            self.agent.reject(proposal_id)
            if self.journal is not None:
                self.journal.transition(proposal_id, preview.digest,
                                        from_state="pending_review", to_state="rejected")
            del self._waiting[proposal_id]
            return {"status": "rejected", "tool": preview.tool}
        # Persist ambiguous dispatch BEFORE calling the tool. On crash this
        # becomes needs_reconciliation; never call tool again automatically.
        if self.journal is not None:
            self.journal.transition(proposal_id, preview.digest,
                                    from_state="pending_review",
                                    to_state="dispatch_uncertain")
        del self._waiting[proposal_id]
        try:
            if preview.mutates:
                token = self.agent.approve(proposal_id)
                # Approval token lives only in process memory.
                result = self.agent.execute(proposal_id, approval_token=token)
            else:
                result = self.agent.execute(proposal_id)
        except BaseException:
            if self.journal is not None:
                self.journal.transition(proposal_id, preview.digest,
                                        from_state="dispatch_uncertain",
                                        to_state="failed_uncertain")
            raise
        if self.journal is not None:
            self.journal.transition(proposal_id, preview.digest,
                                    from_state="dispatch_uncertain", to_state="completed")
        return {"status": result.status, "tool": result.tool,
                "output": result.output}

    def reject_all_pending(self):
        """On UI close: reject staged proposals that the UI still owns."""
        for proposal_id, preview in tuple(self._waiting.items()):
            try:
                self.decide(proposal_id, preview.digest, approved=False)
            except AgentRejected:
                self._waiting.pop(proposal_id, None)

    def status(self):
        raw = self.agent.snapshot()
        return {"pending_approvals": len(self._waiting),
                "steps_used": raw["steps_used"],
                "steps_limit": raw["steps_limit"],
                "stored_synthetic_notes": raw["stored_synthetic_notes"],
                "live_actions": False, "authenticated_identity": False}
