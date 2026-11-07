"""Evidence-gated local procedural learning. No model/tool/network execution.

IMPORTANT: verified_by_host is a trusted-caller assertion, NOT authentication.
Do not expose this kernel to untrusted models, plugins, or public APIs.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import secrets
import sqlite3

_NAME = re.compile(r"\A[a-z][a-z0-9_-]{1,63}\Z")
_SHA = re.compile(r"\A[0-9a-f]{64}\Z")

class LearningRejected(ValueError):
    pass

def _now():
    return datetime.now(timezone.utc).isoformat()

def _family(name):
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise LearningRejected("Invalid skill family")
    return name

class LearningKernel:
    """Stores outcome digests and promotes only independently evaluated skill text.

    Skill text is data, not a higher-trust instruction or a tool permission.
    The application must own the evaluator and protect its held-out cases.
    """
    def __init__(self, path):
        path = Path(path)
        if path.suffix not in (".sqlite", ".sqlite3", ".db") or not path.parent.is_dir():
            raise LearningRejected("SQLite path requires an existing directory")
        self.db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS outcomes(
            id TEXT PRIMARY KEY, family TEXT NOT NULL, task_hash TEXT NOT NULL,
            evidence_hash TEXT NOT NULL, succeeded INTEGER NOT NULL,
            created_at TEXT NOT NULL, UNIQUE(family,task_hash));
        CREATE TABLE IF NOT EXISTS skills(
            id TEXT PRIMARY KEY, family TEXT NOT NULL, body TEXT NOT NULL,
            parent_id TEXT REFERENCES skills(id), sources_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN
                ('candidate','active','superseded','rejected')),
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS active_skills(
            family TEXT PRIMARY KEY, skill_id TEXT NOT NULL REFERENCES skills(id));
        CREATE TABLE IF NOT EXISTS evaluations(
            skill_id TEXT PRIMARY KEY REFERENCES skills(id),
            suite_hash TEXT NOT NULL, cases INTEGER NOT NULL,
            baseline_pass INTEGER NOT NULL, candidate_pass INTEGER NOT NULL,
            regressions INTEGER NOT NULL, accepted INTEGER NOT NULL,
            evaluated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS learning_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL,
            family TEXT NOT NULL, object_id TEXT NOT NULL, created_at TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _audit(self, event, family, ident):
        self.db.execute(
            "INSERT INTO learning_audit(event,family,object_id,created_at)"
            " VALUES(?,?,?,?)", (event, family, ident, _now()))

    def record_verified_outcome(self, family, task_id, evidence_sha256,
                                *, succeeded, verified_by_host=False):
        family = _family(family)
        if (not isinstance(task_id, str) or not 1 <= len(task_id) <= 256
            or not isinstance(evidence_sha256, str)
            or not _SHA.fullmatch(evidence_sha256)
            or type(succeeded) is not bool or verified_by_host is not True):
            raise LearningRejected("A trusted verified outcome is required")
        ident = secrets.token_hex(16)
        try:
            self.db.execute(
                "INSERT INTO outcomes VALUES(?,?,?,?,?,?)",
                (ident, family, sha256(task_id.encode()).hexdigest(),
                 evidence_sha256, int(succeeded), _now()))
        except sqlite3.IntegrityError:
            raise LearningRejected("Duplicate task receipt") from None
        self._audit("outcome_recorded", family, ident)
        return ident

    def _active(self, family):
        return self.db.execute(
            "SELECT s.* FROM skills s JOIN active_skills a ON a.skill_id=s.id "
            "WHERE a.family=?", (family,)).fetchone()

    def active_skill(self, family):
        row = self._active(_family(family))
        if row is None:
            return None
        return {"id": row["id"], "family": row["family"], "text": row["body"],
                "trust": "untrusted_procedural_reference"}

    def propose_skill(self, family, body, outcome_ids):
        family = _family(family)
        if (not isinstance(body, str) or not 20 <= len(body.strip()) <= 4000
            or any(ord(ch) < 32 and ch not in "\t\n" for ch in body)):
            raise LearningRejected("Invalid skill text")
        body = body.strip()
        if (type(outcome_ids) is not list or not 2 <= len(outcome_ids) <= 20
            or len(set(outcome_ids)) != len(outcome_ids)
            or any(not isinstance(x, str) or not re.fullmatch(r"[a-f0-9]{32}", x)
                   for x in outcome_ids)):
            raise LearningRejected("Two to twenty distinct verified sources required")
        marks = ",".join("?" for _ in outcome_ids)
        found = self.db.execute(
            "SELECT COUNT(*) FROM outcomes WHERE family=? AND succeeded=1 "
            "AND id IN (" + marks + ")", [family, *outcome_ids]).fetchone()[0]
        if found != len(outcome_ids):
            raise LearningRejected("Source evidence unavailable or unsuccessful")
        active = self._active(family)
        if active is not None and active["body"] == body:
            raise LearningRejected("Identical to active skill")
        ident = secrets.token_hex(16)
        self.db.execute(
            "INSERT INTO skills VALUES(?,?,?,?,?,?,?)",
            (ident, family, body, active["id"] if active else None,
             json.dumps(sorted(outcome_ids)), "candidate", _now()))
        self._audit("skill_proposed", family, ident)
        return ident

    def evaluate_and_select(self, candidate_id, case_ids, evaluator):
        """Compare baseline and candidate on identical host-held-out cases.

        evaluator(body, case_id) must return bool and be independent of the
        model proposing a skill. Zero regressions + >=1 new success required.
        """
        if (not isinstance(candidate_id, str)
            or not re.fullmatch(r"[a-f0-9]{32}", candidate_id)
            or type(case_ids) is not tuple or not 5 <= len(case_ids) <= 40
            or len(set(case_ids)) != len(case_ids)
            or any(not isinstance(c, str) or not 1 <= len(c) <= 128
                   for c in case_ids) or not callable(evaluator)):
            raise LearningRejected("Trusted bounded evaluation inputs required")
        candidate = self.db.execute(
            "SELECT * FROM skills WHERE id=?", (candidate_id,)).fetchone()
        if candidate is None or candidate["status"] != "candidate":
            raise LearningRejected("Candidate unavailable")
        family = candidate["family"]
        current = self._active(family)
        current_id = current["id"] if current else None
        if candidate["parent_id"] != current_id:
            raise LearningRejected("Candidate baseline is stale")
        baseline_text = current["body"] if current else ""
        outcomes = []
        for case in case_ids:
            b = evaluator(baseline_text, case)
            c = evaluator(candidate["body"], case)
            if type(b) is not bool or type(c) is not bool:
                raise LearningRejected("Evaluator must return bool")
            outcomes.append((b, c))
        baseline_pass = sum(b for b, _ in outcomes)
        candidate_pass = sum(c for _, c in outcomes)
        regressions = sum(b and not c for b, c in outcomes)
        accepted = candidate_pass > baseline_pass and regressions == 0
        suite_hash = sha256(json.dumps(case_ids).encode()).hexdigest()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current_now = self._active(family)
            now_id = current_now["id"] if current_now else None
            state = self.db.execute(
                "SELECT status FROM skills WHERE id=?", (candidate_id,)).fetchone()
            if now_id != current_id or state is None or state[0] != "candidate":
                raise LearningRejected("Concurrent change; results discarded")
            self.db.execute(
                "INSERT INTO evaluations VALUES(?,?,?,?,?,?,?,?)",
                (candidate_id, suite_hash, len(case_ids), baseline_pass,
                 candidate_pass, regressions, int(accepted), _now()))
            if accepted:
                if current_id:
                    self.db.execute(
                        "UPDATE skills SET status='superseded' WHERE id=?",
                        (current_id,))
                self.db.execute(
                    "UPDATE skills SET status='active' WHERE id=?",
                    (candidate_id,))
                self.db.execute(
                    "INSERT INTO active_skills VALUES(?,?) "
                    "ON CONFLICT(family) DO UPDATE SET skill_id=excluded.skill_id",
                    (family, candidate_id))
            else:
                self.db.execute(
                    "UPDATE skills SET status='rejected' WHERE id=?",
                    (candidate_id,))
            self._audit("skill_promoted" if accepted else "skill_rejected",
                        family, candidate_id)
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return {"accepted": accepted, "baseline_passes": baseline_pass,
                "candidate_passes": candidate_pass,
                "regressions": regressions, "suite_sha256": suite_hash}

    def rollback(self, family, target_id):
        family = _family(family)
        old = self._active(family)
        if old is None or not isinstance(target_id, str) or target_id == old["id"]:
            raise LearningRejected("No alternative active version")
        target = self.db.execute(
            "SELECT status FROM skills WHERE id=? AND family=?",
            (target_id, family)).fetchone()
        if target is None or target[0] != "superseded":
            raise LearningRejected("Rollback needs a previously accepted version")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("UPDATE skills SET status='superseded' WHERE id=?",
                            (old["id"],))
            self.db.execute("UPDATE skills SET status='active' WHERE id=?",
                            (target_id,))
            self.db.execute("UPDATE active_skills SET skill_id=? WHERE family=?",
                            (target_id, family))
            self._audit("skill_rollback", family, target_id)
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return target_id

    def audit_events(self, limit=20):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise LearningRejected("Invalid audit limit")
        return [dict(r) for r in self.db.execute(
            "SELECT event,family,object_id,created_at FROM learning_audit "
            "ORDER BY id DESC LIMIT ?", (limit,))]
