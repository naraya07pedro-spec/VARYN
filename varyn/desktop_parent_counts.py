"""17S-20 trusted desktop owner review of a VARYN-generated synthetic count.

A real Tk dialog can provide the owner's decision, but automated UI tests
simulate that dialog. This is LOCAL parent-side execution: not AppContainer,
not a private document tool, not model/upload/sync, and not a production grant.
The journal lives only as long as this disposable demo fixture.
"""
from varyn.bounded_broker_protocol import BrokerRejected
from varyn.durable_broker_journal import DurableOneShotJournal
from varyn.parent_synthetic_read_broker import ParentSyntheticReadBroker
from varyn.synthetic_fixture import SyntheticParentCountsFixture


class DesktopParentCountsAction:
    def __init__(self, *, clock=None):
        self.fixture = SyntheticParentCountsFixture()
        self.journal = None
        self.broker = None
        self._closed = False
        try:
            self.journal = DurableOneShotJournal(
                str(self.fixture.root / "owner-demo-journal.sqlite"))
            self.broker = ParentSyntheticReadBroker(
                self.fixture.root, self.journal, clock=clock,
                desktop_fixture=self.fixture)
        except BaseException:
            if self.journal is not None:
                self.journal.close()
            self.fixture.close()
            raise

    def preview(self):
        if self._closed:
            raise BrokerRejected("Owner review already closed")
        return self.broker.preview()

    def decide_and_run(self, preview, *, approved):
        if self._closed:
            raise BrokerRejected("Owner review already closed")
        if type(approved) is not bool:
            raise BrokerRejected("Owner decision must be explicit")
        if not self.broker.owner_decide(
                preview.request_id, preview.digest, approved=approved):
            return {"status": "rejected", "external_upload": False}
        # Only the trusted parent sees the validated integers.
        request = self.broker.claim_and_prepare()
        if request["action"] != "sum_synthetic_counts":
            raise BrokerRejected("Unexpected trusted local action")
        total = self.broker.complete_local_synthetic()
        return {
            "status": "completed", "total": total,
            "synthetic_only": True, "os_sandbox": False,
            "external_upload": False,
        }

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self.broker is not None:
                self.broker.revoke()
        finally:
            try:
                if self.journal is not None:
                    self.journal.close()
            finally:
                self.fixture.close()
