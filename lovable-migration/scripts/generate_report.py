#!/usr/bin/env python3
"""Render the migration handover report from a JSON record of what was done.

Usage:
  generate_report.py <migration-report.json> [--output MIGRATION_REPORT.md]

Start from assets/report-template.json, fill it in as the migration progresses, and
render it at handover. The overall status is computed, not written by hand: the
report says "complete" only when every required check passed (or is not
applicable), every route was migrated or changed with approval, and every visual
difference was explained and approved. Requires Python 3.8+.
"""
import argparse
import json
import sys

RESULTS = ("PASS", "FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE")
PAGE_STATUSES = ("migrated", "changed-with-approval", "removed-with-approval", "missing", "in-progress")


def table(headers, rows):
    if not rows:
        return ["_None._", ""]
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in row) + " |" for row in rows]
    return out + [""]


def code_block(text):
    return ["```text", (text or "(not recorded)").rstrip(), "```", ""]


def compute_status(report):
    problems = []
    for check in report.get("checks", []):
        if check.get("result") not in RESULTS:
            problems.append("check %r has invalid result %r" % (check.get("name"), check.get("result")))
        elif check.get("required", True) and check["result"] not in ("PASS", "NOT_APPLICABLE"):
            problems.append("required check %s is %s" % (check.get("name"), check["result"]))
        if check.get("result") == "NOT_APPLICABLE" and not check.get("evidence"):
            problems.append("check %s is NOT_APPLICABLE without a reason" % check.get("name"))
    if not report.get("checks"):
        problems.append("no checks recorded")
    for page in report.get("pages", []):
        if page.get("status") not in PAGE_STATUSES:
            problems.append("route %s has invalid status %r" % (page.get("route"), page.get("status")))
        elif page["status"] in ("missing", "in-progress"):
            problems.append("route %s is %s" % (page.get("route"), page["status"]))
    if not report.get("pages"):
        problems.append("no routes recorded")
    parity = report.get("visualParity") or {}
    if not parity.get("ran"):
        problems.append("visual parity was not run: %s" % (parity.get("reasonNotRun") or "no reason recorded"))
    for diff in parity.get("differences", []):
        if not (diff.get("explanation") and diff.get("approvedByUser")):
            problems.append("visual difference on %s (%s) is not explained and approved" % (diff.get("route"), diff.get("viewport")))
    for change in report.get("intentionalDifferences", []):
        if not change.get("approvedByUser"):
            problems.append("intentional difference not approved: %s" % change.get("what"))
    return ("complete" if not problems else "incomplete"), problems


def render(report):
    status, problems = compute_status(report)
    project = report.get("project", {})
    config = report.get("configuration", {})
    lines = ["# Frontend migration report: %s" % project.get("name", "(unnamed)"), ""]
    lines += ["**Status: %s**" % ("Complete" if status == "complete" else "Incomplete, see open items"), ""]
    lines += ["- Source (unchanged): `%s`" % project.get("source", "?"),
              "- Migrated project: `%s`" % project.get("target", "?"),
              "- Source classification: %s" % report.get("classification", "?"),
              "- Date: %s" % project.get("date", "?"), ""]
    if report.get("summary"):
        lines += ["## Summary", "", report["summary"], ""]

    lines += ["## Configuration", ""]
    lines += table(["Setting", "Choice"], [(k, v) for k, v in config.items()])

    arch = report.get("architecture", {})
    lines += ["## Architecture", "", "Original:", ""] + code_block(arch.get("before"))
    lines += ["Migrated:", ""] + code_block(arch.get("after"))
    if arch.get("notes"):
        lines += [arch["notes"], ""]

    lines += ["## Routes and pages", ""]
    lines += table(["Route", "Original", "Migrated", "Status", "Notes"],
                   [(p.get("route"), p.get("source"), p.get("target"), p.get("status"), p.get("notes", "")) for p in report.get("pages", [])])

    lines += ["## Extracted components", ""]
    lines += table(["Component", "Path", "Responsibility", "Used by"],
                   [(c.get("name"), c.get("path"), c.get("purpose", ""), ", ".join(c.get("usedBy", []))) for c in report.get("components", [])])
    if report.get("dataFiles"):
        lines += ["## Static data", ""]
        lines += table(["File", "Contents"], [(d.get("path"), d.get("contents")) for d in report["dataFiles"]])

    deps = report.get("dependencies", {})
    lines += ["## Dependency changes", ""]
    rows = [("added", d.get("name"), d.get("reason", "")) for d in deps.get("added", [])]
    rows += [("removed", d.get("name"), d.get("reason", "")) for d in deps.get("removed", [])]
    rows += [("replaced", "%s → %s" % (d.get("from"), d.get("to")), d.get("reason", "")) for d in deps.get("replaced", [])]
    lines += table(["Change", "Package", "Reason"], rows)
    if report.get("removedFiles"):
        lines += ["## Removed from the migrated project", ""]
        lines += table(["Path", "Reason"], [(r.get("path"), r.get("reason")) for r in report["removedFiles"]])

    lines += ["## Checks", ""]
    lines += table(["Check", "Command / procedure", "Result", "Evidence", "Required"],
                   [(c.get("name"), "`%s`" % c.get("command", ""), c.get("result"), c.get("evidence", ""),
                     "yes" if c.get("required", True) else "no") for c in report.get("checks", [])])

    parity = report.get("visualParity") or {}
    lines += ["## Visual parity", ""]
    if parity.get("ran"):
        lines += ["Compared %s route captures at %s with a %s maximum pixel difference ratio: %s passed." % (
            parity.get("captures", "?"), ", ".join(parity.get("viewports", [])) or "?",
            parity.get("maxDiffRatio", "?"), parity.get("passed", "?")), ""]
        lines += table(["Route", "Viewport", "Difference", "Explanation", "Approved"],
                       [(d.get("route"), d.get("viewport"), d.get("diff", ""), d.get("explanation", ""),
                         "yes" if d.get("approvedByUser") else "no") for d in parity.get("differences", [])])
    else:
        lines += ["Not run: %s" % (parity.get("reasonNotRun") or "no reason recorded"), ""]

    if report.get("intentionalDifferences"):
        lines += ["## Intentional differences", ""]
        lines += table(["What", "Why", "Approved"], [(d.get("what"), d.get("why"), "yes" if d.get("approvedByUser") else "no")
                                                    for d in report["intentionalDifferences"]])
    if report.get("externalServices"):
        lines += ["## External services and backend findings", ""]
        lines += table(["Finding", "Where", "Handling"], [(f.get("what"), f.get("where"), f.get("handling"))
                                                          for f in report["externalServices"]])

    commands = report.get("commands", {})
    lines += ["## Commands", ""]
    lines += ["```bash"] + ["# %s\n%s" % (k, v) for k, v in commands.items()] + ["```", ""]
    if report.get("deployment"):
        lines += ["## Deployment notes", ""] + ["- %s" % d for d in report["deployment"]] + [""]

    lines += ["## Known limitations and follow-ups", ""]
    items = ["- %s" % p for p in problems] + ["- %s" % l for l in report.get("limitations", [])]
    items += ["- Follow-up: %s" % f for f in report.get("followUps", [])]
    lines += (items or ["_None._"]) + [""]
    return "\n".join(lines), status


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report")
    parser.add_argument("--output")
    args = parser.parse_args()
    with open(args.report) as handle:
        report = json.load(handle)
    text, status = render(report)
    if args.output:
        with open(args.output, "w") as handle:
            handle.write(text)
        print(json.dumps({"written": args.output, "status": status}))
    else:
        sys.stdout.write(text)
    return 0 if status == "complete" else 2


if __name__ == "__main__":
    sys.exit(main())
