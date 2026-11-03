"""Read-only local storage exposure audit for the unencrypted VARYN prototype.

The result is advisory and NEVER grants access or declares data secure.
Windows DACLs cannot be established from portable stat bits; fail closed.
No path names, usernames, contents, or secrets are emitted in the report.
"""
import argparse
import json
import os
import stat
from pathlib import Path


def _is_windows():
    return os.name == "nt"


def audit_storage(path):
    """Inspect ONE existing SQLite file without reading or changing its contents.

    A secure outcome is impossible at this stage: no encryption or authenticated
    owner identity exists. This method does not use the path as a trust token.
    """
    target = Path(path)
    findings = []
    if target.is_symlink():
        findings.append("symlink_path_rejected")
        return _report(findings, "rejected")
    if not target.exists():
        findings.append("missing_path")
        return _report(findings, "rejected")
    if not target.is_file():
        findings.append("not_regular_file")
        return _report(findings, "rejected")

    # Do not resolve or display the path, and never call sqlite on its content.
    if _is_windows():
        findings.append("windows_acl_not_inspected")
    else:
        mode = target.stat(follow_symlinks=False).st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            findings.append("group_or_other_permissions")
        else:
            findings.append("posix_mode_owner_only")

    findings.extend([
        "database_not_encrypted",
        "owner_label_not_authenticated",
        "backup_policy_not_verified",
    ])
    return _report(findings, "blocked")


def _report(findings, status):
    return {
        "format": "varyn.storage_audit.v1",
        "status": status,
        "ready_for_sensitive_data": False,
        "checks": findings,
        "diagnostic_only": True,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Read-only VARYN storage audit; NEVER proof of security"
    )
    parser.add_argument("--db", required=True, help="Existing SQLite path; not displayed")
    args = parser.parse_args()
    print(json.dumps(audit_storage(args.db), sort_keys=True))


if __name__ == "__main__":
    main()
