#!/usr/bin/env python3
"""Render a human-readable synchronization report from the sync state.

Usage: generate_report.py [--state-dir DIR] [--session ID] [--write]

Uses the active session, or the most recent one. Run `sync_state.py finalize`
(or `finalize --dry-run` for a preview) first so the session has a result.
With --write, saves <state-dir>/reports/<session>.md and commits it to the state
history. Only metadata recorded by sync_state.py is used; no secrets are read.
Requires Python 3.8+.
"""
import argparse
import json
import os
import subprocess
import sys

STATE_DIRNAME = ".lovable-sync"
RESOLVED = {"verified", "already-present", "ignored", "declined", "retained-local"}
CATEGORY_LABELS = {
    "feature": "New features", "ui": "UI changes", "bugfix": "Bug fixes", "validation": "Validation changes",
    "api": "API changes", "database": "Database changes", "auth": "Authentication changes",
    "storage": "Storage changes", "realtime": "Realtime changes", "integration": "Integration changes",
    "dependency": "Dependency updates", "configuration": "Configuration changes",
    "supabase-specific": "Supabase-specific changes", "lovable-tooling": "Lovable tooling changes",
    "docs": "Documentation", "tests": "Tests", "revert": "Reverts", "other": "Other",
}


def locate(explicit):
    if explicit:
        path = os.path.abspath(explicit)
        return path if os.path.basename(path) == STATE_DIRNAME else os.path.join(path, STATE_DIRNAME)
    current = os.getcwd()
    while True:
        if os.path.exists(os.path.join(current, STATE_DIRNAME, "sync-state.json")):
            return os.path.join(current, STATE_DIRNAME)
        parent = os.path.dirname(current)
        if parent == current:
            raise SystemExit("error: no %s/sync-state.json found; pass --state-dir" % STATE_DIRNAME)
        current = parent


def load(path):
    with open(path) as handle:
        return json.load(handle)


def short(commit):
    return (commit or "-")[:12]


def render(state, session):
    units = session["units"]
    result = session.get("result") or {}
    lines = ["# Lovable Synchronization Report", ""]
    lines += ["Session: %s (%s)" % (session["sessionId"], session["status"]), ""]
    lines += ["```text"]
    lines += ["Source:", "  %s/%s" % (state["source"]["path"], session["sourceBranch"]), ""]
    lines += ["Previous synchronized commit:", "  %s" % short(session["startCommit"]), ""]
    lines += ["Current upstream commit:", "  %s" % short(session["targetCommit"]), ""]
    lines += ["New commits detected:", "  %d" % len(session["commits"]), ""]

    lines += ["Changes analyzed:"]
    categories = {}
    for unit in units:
        categories[unit.get("category") or "other"] = categories.get(unit.get("category") or "other", 0) + 1
    lines += ["  %s: %d" % (CATEGORY_LABELS.get(k, k), v) for k, v in sorted(categories.items())] or ["  none recorded"]
    lines += [""]

    for role in ("frontend", "backend"):
        role_units = [u for u in units if role in u.get("targets", [])]
        implemented = sum(1 for u in role_units if u["status"] == "verified")
        present = sum(1 for u in role_units if u["status"] == "already-present")
        waiting = sum(1 for u in role_units if u["status"] not in RESOLVED)
        lines += ["%s:" % role.capitalize(), "  Implemented: %d" % implemented, "  Already present: %d" % present]
        if waiting:
            lines += ["  Not finished: %d" % waiting]
        lines += [""]

    skipped = [u for u in units if u["status"] in ("ignored", "declined", "retained-local")]
    lines += ["Ignored or declined:"] + (["  %s (%s): %s" % (u["title"] or u["id"], u["status"],
                                                           u.get("reason") or u.get("decision") or "")
                                          for u in skipped] or ["  none"]) + [""]
    open_conflicts = [c for c in session["conflicts"] if c["status"] != "resolved"]
    lines += ["Conflicts:", "  %d open, %d resolved" % (len(open_conflicts),
                                                       len(session["conflicts"]) - len(open_conflicts)), ""]
    lines += ["Validation:"]
    labels = {"PASS": "Passed", "FAIL": "Failed", "BLOCKED": "Blocked", "NOT_RUN": "Not run",
              "NOT_APPLICABLE": "Not applicable"}
    lines += ["  %s %s: %s" % (v["scope"].capitalize(), v["name"], labels[v["result"]])
              for v in session["validations"]] or ["  none recorded"]
    lines += [""]
    status_text = {"completed": "Completed successfully", "partial": "Partially completed (checkpoint moved only "
                   "over fully verified commits)", "in-progress": "Not finished (checkpoint unchanged)",
                   "abandoned": "Abandoned (checkpoint unchanged)"}
    lines += ["Synchronization:", "  %s" % status_text.get(session["status"], session["status"]), ""]
    lines += ["New checkpoint:", "  %s" % short(result.get("checkpointAfter") or state["source"]["lastSyncedCommit"])]
    lines += ["```", ""]

    lines += ["## Work units", "", "| Unit | Category | Upstream commits | Targets | Status | Destination commits |",
              "| --- | --- | --- | --- | --- | --- |"]
    for unit in units:
        dest = ", ".join(["fe:" + short(c) for c in unit["frontendCommits"]] +
                         ["be:" + short(c) for c in unit["backendCommits"]]) or "-"
        lines.append("| %s %s | %s | %s | %s | %s | %s |" % (
            unit["id"], unit.get("title") or "", unit.get("category") or "-",
            ", ".join(short(c) for c in unit["commits"]), ", ".join(unit.get("targets", [])) or "-",
            unit["status"], dest))
    lines += [""]

    if session["conflicts"]:
        lines += ["## Conflicts", ""]
        for c in session["conflicts"]:
            lines += ["- **%s** (%s, unit %s): %s" % (c["id"], c["status"], c.get("unit") or "-", c.get("feature")),
                      "  - Upstream: %s" % c.get("upstreamChange"), "  - Existing: %s" % c.get("existing"),
                      "  - Reason: %s" % c.get("reason"), "  - Proposal: %s" % c.get("proposal"),
                      "  - Impact: %s" % c.get("impact"),
                      "  - Approval: %s" % ("required" if c.get("needsApproval") else "not required") +
                      ("; resolution %s%s" % (c["resolution"], ", user-approved" if c.get("userApproved") else "")
                       if c.get("resolution") else "")]
        lines += [""]

    if session["validations"]:
        lines += ["## Validation evidence", "", "| Scope | Check | Command | Result | Evidence | At commit |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for v in session["validations"]:
            lines.append("| %s | %s | `%s` | %s | %s | %s |" % (v["scope"], v["name"], v["command"], v["result"],
                                                               v["evidence"], short(v.get("head"))))
        lines += [""]

    remaining = [u for u in units if u["status"] not in RESOLVED]
    problems = result.get("problems") or []
    uncovered = result.get("unresolvedCommits") or []
    lines += ["## Remaining issues and next actions", ""]
    if not (remaining or problems or uncovered or open_conflicts):
        lines += ["None. Review and merge the sync branches; nothing was pushed or deployed.", ""]
    for unit in remaining:
        lines.append("- Unit %s %s is %s: %s" % (unit["id"], unit.get("title") or "", unit["status"],
                                                 unit.get("reason") or "finish, verify and record it"))
    for problem in problems:
        lines.append("- %s" % problem)
    if uncovered:
        lines.append("- Upstream commits not yet resolved: %s" % ", ".join(short(c) for c in uncovered))
    workspaces = session.get("workspaces") or {}
    if workspaces:
        lines += ["", "Work branches: " + ", ".join("%s `%s` in `%s`" % (r, w["branch"], w["path"])
                                                    for r, w in sorted(workspaces.items()))]
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state-dir")
    parser.add_argument("--session")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    state_dir = locate(args.state_dir)
    state = load(os.path.join(state_dir, "sync-state.json"))
    session_id = args.session or state.get("activeSession") or (state["history"][-1]["sessionId"]
                                                                if state["history"] else None)
    if not session_id:
        sys.stderr.write("error: no sessions yet\n")
        return 1
    session = load(os.path.join(state_dir, "sessions", session_id + ".json"))
    text = render(state, session)
    if args.write:
        path = os.path.join(state_dir, "reports", session_id + ".md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as handle:
            handle.write(text)
        os.replace(tmp, path)
        subprocess.run(["git", "-C", state_dir, "add", path], capture_output=True)
        identity = []
        if subprocess.run(["git", "-C", state_dir, "config", "user.email"], capture_output=True).returncode != 0:
            identity = ["-c", "user.name=sync-lovable-app", "-c", "user.email=sync-lovable-app@localhost"]
        subprocess.run(["git", "-C", state_dir, *identity, "commit", "-q", "-m", "%s: report" % session_id],
                       capture_output=True)
        sys.stderr.write("written: %s\n" % path)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
