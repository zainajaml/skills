#!/usr/bin/env python3
"""Deterministic Git history facts for the upstream Lovable repository.

Usage:
  analyze_commits.py --repo <source> --base <checkpoint> --target <ref> [--output FILE]
  analyze_commits.py --repo <source> --find-equivalent <old-commit> --target <ref>

The first form checks the range (base exists, is an ancestor, shallow clone, no new
commits) and lists every commit in topological order with changed files, renames,
deletions, path-based hints, Supabase/Lovable signals found in added lines, SQL
objects touched, dependency changes, env variable *names*, reverts, cherry-picks
and duplicate patches. The second form looks for the rewritten counterpart of a
commit after a rebase or force push.

Read-only: never checks out, fetches or writes in the repository. Never prints
diff content, and never reads .env files. The output is evidence for the agent;
the agent still reads the diffs to understand intent. Requires Python 3.8+ and git.
"""
import argparse
import json
import os
import re
import subprocess
import sys

LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock"}

PATH_HINTS = [
    (r"(^|/)\.env(\.|$)", "env-file"),
    (r"^supabase/migrations/", "database-migration"),
    (r"^supabase/functions/", "edge-function"),
    (r"^supabase/config\.toml$", "supabase-config"),
    (r"^supabase/seed", "database-seed"),
    (r"integrations/supabase/types\.ts$", "supabase-generated-types"),
    (r"integrations/supabase/client\.ts$", "supabase-client"),
    (r"(^|/)\.lovable/|lovable", "lovable-tooling"),
    (r"(^|/)package\.json$", "dependencies"),
    (r"(^|/)(vite|next|nuxt|astro)\.config\.|(^|/)tsconfig.*\.json$|(^|/)eslint|(^|/)wrangler\.", "build-config"),
    (r"(^|/)tailwind\.config\.|(^|/)postcss\.config\.|(^|/)components\.json$", "design-config"),
    (r"\.(css|scss|sass|less)$", "styles"),
    (r"(^|/)(pages|routes|app)/", "routes"),
    (r"(^|/)App\.(t|j)sx?$|(^|/)router\.|routeTree", "routes"),
    (r"(^|/)components/ui/", "ui-primitive"),
    (r"(^|/)components/", "ui"),
    (r"(^|/)hooks/", "hooks"),
    (r"(^|/)(lib|utils|services|api)/", "shared-logic"),
    (r"(schema|validation|validator)s?\.(t|j)sx?$|(^|/)schemas?/", "validation"),
    (r"\.server\.(t|j)sx?$|\.functions\.(t|j)sx?$", "server-function"),
    (r"(^|/)(public|assets)/", "assets"),
    (r"\.(test|spec)\.|(^|/)(tests?|__tests__|e2e)/", "tests"),
    (r"\.mdx?$", "docs"),
]

CONTENT_SIGNALS = {
    "supabase-query": r"\.from\(\s*['\"`]",
    "supabase-rpc": r"\.rpc\(",
    "supabase-auth": r"\bsupabase\.auth\b|\.auth\.(signIn|signUp|signOut|getUser|getSession|onAuthStateChange|resetPassword|updateUser|admin)",
    "supabase-storage": r"\.storage\b",
    "supabase-realtime": r"\.channel\(|postgres_changes|\.subscribe\(",
    "edge-function-call": r"functions\.invoke\(",
    "lovable-ai": r"ai\.gateway\.lovable\.dev|LOVABLE_API_KEY",
    "service-role": r"service_role|SERVICE_ROLE",
    "rls": r"(?i)\b(create|alter|drop)\s+policy\b|enable\s+row\s+level\s+security",
    "auth-schema": r"auth\.uid\(\)|auth\.jwt\(\)|auth\.users",
    "fetch-call": r"\bfetch\(|axios\.",
    "validation-lib": r"\bz\.(object|string|number|enum|array)\(|yup\.|useForm\(",
}

NAME_PATTERNS = {
    "tables": r"\.from\(\s*['\"`]([\w.]+)['\"`]",
    "rpcs": r"\.rpc\(\s*['\"`]([\w.]+)['\"`]",
    "buckets": r"storage\s*\.from\(\s*['\"`]([\w.-]+)['\"`]",
    "edgeFunctions": r"functions\.invoke\(\s*['\"`]([\w-]+)['\"`]",
    "envVars": r"import\.meta\.env\.(\w+)|process\.env\.(\w+)|Deno\.env\.get\(\s*['\"`](\w+)",
}

SQL_PATTERN = re.compile(
    r"(?i)\b(create|alter|drop)\s+(?:or\s+replace\s+)?(?:unique\s+)?"
    r"(table|policy|function|trigger|type|index|view|materialized\s+view|extension|schema|sequence)\s+"
    r"(?:if\s+(?:not\s+)?exists\s+)?(\"?[\w.]+\"?)")
SQL_COLUMN = re.compile(r"(?i)\b(add|drop|alter|rename)\s+column\s+(?:if\s+(?:not\s+)?exists\s+)?(\"?\w+\"?)")


def git(repo, *args, check=True):
    result = subprocess.run(["git", "-C", repo, "-c", "core.quotePath=false", *args],
                            capture_output=True, text=True, errors="replace")
    if check and result.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), result.stderr.strip()))
    return result.stdout if result.returncode == 0 else None


def resolve(repo, ref):
    out = git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}", check=False)
    return out.strip() if out else None


def is_ancestor(repo, a, b):
    return subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", a, b],
                          capture_output=True).returncode == 0


def path_hints(path):
    hints = []
    for pattern, hint in PATH_HINTS:
        if re.search(pattern, path) and hint not in hints:
            hints.append(hint)
    return hints or ["other"]


def is_sensitive(path):
    return bool(re.search(r"(^|/)\.env(\.|$)", path)) and not path.endswith(".example")


def changed_files(repo, commit, parent):
    args = ["diff-tree", "-r", "-M", "--no-commit-id", "--name-status", "-z"]
    out = git(repo, *(args + ([parent, commit] if parent else ["--root", commit])))
    parts = out.split("\0")
    files, i = [], 0
    while i < len(parts) - 1:
        status = parts[i]
        if not status:
            i += 1
            continue
        if status[0] in "RC":
            files.append({"status": status[0], "similarity": int(status[1:] or 0),
                          "oldPath": parts[i + 1], "path": parts[i + 2]})
            i += 3
        else:
            files.append({"status": status[0], "path": parts[i + 1]})
            i += 2
    numstat = git(repo, *(["diff-tree", "-r", "-M", "--no-commit-id", "--numstat", "-z"] +
                          ([parent, commit] if parent else ["--root", commit])))
    stats, parts, i = {}, numstat.split("\0"), 0
    while i < len(parts) - 1:
        fields = parts[i].split("\t")
        if len(fields) == 3 and fields[2] == "":
            path, i = parts[i + 2], i + 3
        elif len(fields) == 3:
            path, i = fields[2], i + 1
        else:
            i += 1
            continue
        stats[path] = (fields[0], fields[1])
    for entry in files:
        added, deleted = stats.get(entry["path"], ("0", "0"))
        entry["added"] = None if added == "-" else int(added)
        entry["deleted"] = None if deleted == "-" else int(deleted)
        entry["hints"] = path_hints(entry["path"])
        if is_sensitive(entry["path"]):
            entry["sensitive"] = True
    return files


def scan_added_lines(repo, commit, parent, files):
    """Signals and names from added/removed lines; content itself is never returned."""
    paths = [f["path"] for f in files
             if not f.get("sensitive") and os.path.basename(f["path"]) not in LOCKFILES and f["status"] != "D"]
    signals, names, sql = set(), {k: set() for k in NAME_PATTERNS}, []
    if not paths:
        return [], {}, []
    for start in range(0, len(paths), 100):
        chunk = paths[start:start + 100]
        rng = [parent, commit] if parent else ["--root", commit]
        out = git(repo, "diff-tree", "-p", "-M", "--no-commit-id", "-U0", "--no-ext-diff", *rng, "--", *chunk,
                  check=False) or ""
        current = None
        for line in out.splitlines():
            if line.startswith("+++ "):
                current = line[6:] if line.startswith("+++ b/") else None
                continue
            if not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
                continue
            body = line[1:]
            for signal, pattern in CONTENT_SIGNALS.items():
                if re.search(pattern, body):
                    signals.add(signal)
            for key, pattern in NAME_PATTERNS.items():
                for match in re.finditer(pattern, body):
                    value = next((g for g in match.groups() if g), None)
                    if value:
                        names[key].add(value)
            if current and current.endswith(".sql"):
                for match in SQL_PATTERN.finditer(body):
                    op = "%s %s %s" % (match.group(1).lower(), " ".join(match.group(2).lower().split()),
                                       match.group(3).strip('"'))
                    sql.append(("+" if line[0] == "+" else "-") + op)
                for match in SQL_COLUMN.finditer(body):
                    sql.append(("+" if line[0] == "+" else "-") + "%s column %s" % (match.group(1).lower(),
                                                                                    match.group(2).strip('"')))
    sql = list(dict.fromkeys(sql))
    return sorted(signals), {k: sorted(v) for k, v in names.items() if v}, sql


def dependency_changes(repo, commit, parent, files):
    changes = []
    for entry in files:
        if os.path.basename(entry["path"]) != "package.json":
            continue
        def load(rev, path):
            text = git(repo, "show", "%s:%s" % (rev, path), check=False) if rev else None
            try:
                return json.loads(text) if text else {}
            except ValueError:
                return {}
        before = load(parent, entry.get("oldPath", entry["path"]))
        after = load(commit, entry["path"]) if entry["status"] != "D" else {}
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            old, new = before.get(section, {}) or {}, after.get(section, {}) or {}
            for name in sorted(set(old) | set(new)):
                if old.get(name) != new.get(name):
                    changes.append({"file": entry["path"], "section": section, "name": name,
                                    "from": old.get(name), "to": new.get(name)})
        old_scripts, new_scripts = before.get("scripts", {}) or {}, after.get("scripts", {}) or {}
        for name in sorted(set(old_scripts) | set(new_scripts)):
            if old_scripts.get(name) != new_scripts.get(name):
                changes.append({"file": entry["path"], "section": "scripts", "name": name,
                                "from": old_scripts.get(name), "to": new_scripts.get(name)})
    return changes


def patch_id(repo, commit):
    show = subprocess.run(["git", "-C", repo, "show", "--format=", commit], capture_output=True)
    result = subprocess.run(["git", "-C", repo, "patch-id", "--stable"], input=show.stdout, capture_output=True)
    out = result.stdout.decode().split()
    return out[0] if out else None


def read_commits(repo, *log_args):
    """Commits from `git log <log_args>`, oldest first for a range."""
    fmt = "%H%x1f%P%x1f%an%x1f%aI%x1f%cI%x1f%s%x1f%b%x1e"
    out = git(repo, "log", "--format=" + fmt, *log_args)
    commits = []
    for record in out.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        fields = record.split("\x1f")
        commits.append({"hash": fields[0], "parents": fields[1].split(), "author": fields[2],
                        "authoredAt": fields[3], "committedAt": fields[4], "subject": fields[5],
                        "body": fields[6].strip()})
    return commits


def analyze(repo, base, target):
    report = {"repository": os.path.abspath(repo), "checks": {}, "commits": []}
    shallow = (git(repo, "rev-parse", "--is-shallow-repository") or "").strip() == "true"
    report["checks"]["shallow"] = shallow
    target_hash = resolve(repo, target)
    base_hash = resolve(repo, base)
    report["target"] = {"ref": target, "commit": target_hash}
    report["base"] = {"ref": base, "commit": base_hash}
    if target_hash is None:
        report["status"] = "target-missing"
        return report
    if base_hash is None:
        report["status"] = "base-missing"
        report["checks"]["hint"] = ("checkpoint not in local history: shallow clone, unfetched history or "
                                    "rewritten branch; ask the user before fetching or unshallowing")
        return report
    if base_hash == target_hash:
        report["status"] = "no-new-commits"
        return report
    if not is_ancestor(repo, base_hash, target_hash):
        merge_base = (git(repo, "merge-base", base_hash, target_hash, check=False) or "").strip() or None
        report["status"] = "base-not-ancestor"
        report["divergence"] = {
            "mergeBase": merge_base,
            "onlyInOldHistory": int(git(repo, "rev-list", "--count", "%s..%s" % (target_hash, base_hash)).strip()),
            "onlyInTarget": int(git(repo, "rev-list", "--count", "%s..%s" % (base_hash, target_hash)).strip()),
        }
        report["checks"]["hint"] = "history was rewritten; run --find-equivalent for the checkpoint"
        return report

    report["status"] = "ok"
    commits = read_commits(repo, "--topo-order", "--reverse", "%s..%s" % (base_hash, target_hash))
    by_patch, file_touches = {}, {}
    for commit in commits:
        parent = commit["parents"][0] if commit["parents"] else None
        commit["isMerge"] = len(commit["parents"]) > 1
        files = changed_files(repo, commit["hash"], parent)
        commit["files"] = files
        if commit["isMerge"]:
            brought = git(repo, "rev-list", "%s..%s" % (parent, commit["hash"])).split()
            commit["mergedCommits"] = [h for h in brought if h != commit["hash"]]
            commit["note"] = ("merge: files are the first-parent diff; the merged commits are listed "
                              "separately, so inspect only the conflict resolution (git show --remerge-diff)")
            commit["signals"], commit["names"], commit["sql"], commit["dependencyChanges"] = [], {}, [], []
        else:
            commit["signals"], commit["names"], commit["sql"] = scan_added_lines(repo, commit["hash"], parent, files)
            commit["dependencyChanges"] = dependency_changes(repo, commit["hash"], parent, files)
            pid = patch_id(repo, commit["hash"])
            commit["patchId"] = pid
            if pid:
                by_patch.setdefault(pid, []).append(commit["hash"])
        commit["hints"] = sorted({h for f in files for h in f["hints"]})
        commit["destructive"] = any(f["status"] == "D" for f in files) or any(s.startswith("+drop") for s in commit["sql"])
        commit["reverts"] = re.findall(r"This reverts commit ([0-9a-f]{7,40})", commit["body"])
        commit["cherryPickedFrom"] = re.findall(r"cherry picked from commit ([0-9a-f]{7,40})", commit["body"])
        commit["sensitiveFilesChanged"] = [f["path"] for f in files if f.get("sensitive")]
        for entry in files:
            file_touches.setdefault(entry["path"], []).append(commit["hash"])
            if entry.get("oldPath"):
                file_touches.setdefault(entry["oldPath"], []).append(commit["hash"])

    in_range = {c["hash"] for c in commits}
    report["commits"] = commits
    report["summary"] = {
        "commitCount": len(commits),
        "mergeCommits": sum(1 for c in commits if c["isMerge"]),
        "netDiff": (git(repo, "diff", "--shortstat", base_hash, target_hash) or "").strip(),
        "filesTouchedByMultipleCommits": {p: h for p, h in sorted(file_touches.items()) if len(set(h)) > 1},
        "renames": [{"from": f["oldPath"], "to": f["path"], "commit": c["hash"]}
                    for c in commits for f in c["files"] if f["status"] == "R"],
        "deletedFiles": [{"path": f["path"], "commit": c["hash"]} for c in commits for f in c["files"]
                         if f["status"] == "D"],
        "duplicatePatches": [h for h in by_patch.values() if len(h) > 1],
        "revertsInRange": [{"commit": c["hash"], "reverts": r,
                            "revertedCommitInRange": any(x.startswith(r) for x in in_range)}
                           for c in commits for r in c["reverts"]],
        "hints": sorted({h for c in commits for h in c["hints"]}),
        "signals": sorted({s for c in commits for s in c["signals"]}),
        "envVarsReferenced": sorted({v for c in commits for v in c["names"].get("envVars", [])}),
        "sensitiveFilesChanged": sorted({p for c in commits for p in c["sensitiveFilesChanged"]}),
    }
    return report


def find_equivalent(repo, old, target, limit):
    old_hash = resolve(repo, old)
    target_hash = resolve(repo, target)
    result = {"old": old, "oldCommit": old_hash, "target": target, "targetCommit": target_hash, "candidates": []}
    if not old_hash or not target_hash:
        result["status"] = "missing-object"
        result["hint"] = ("the old commit object is not available locally (check the reflog or another clone); "
                          "without it, only subject/date matching from recorded metadata is possible")
        return result
    old_info = read_commits(repo, "-1", old_hash)[0]
    old_pid = patch_id(repo, old_hash)
    old_tree = git(repo, "rev-parse", old_hash + "^{tree}").strip()
    for commit in read_commits(repo, "-n", str(limit), target_hash):
        evidence = []
        if old_pid and patch_id(repo, commit["hash"]) == old_pid:
            evidence.append("same patch-id")
        if commit["subject"] == old_info["subject"]:
            evidence.append("same subject")
        if commit["authoredAt"] == old_info["authoredAt"] and commit["author"] == old_info["author"]:
            evidence.append("same author and author date")
        if evidence:
            tree = git(repo, "rev-parse", commit["hash"] + "^{tree}").strip()
            result["candidates"].append({"commit": commit["hash"], "subject": commit["subject"],
                                         "evidence": evidence, "treeMatches": tree == old_tree})
    result["status"] = "candidates" if result["candidates"] else "no-match"
    result["note"] = ("a candidate is evidence, not proof; the user approves any rebaseline. A matching tree means "
                      "the code is identical at that point.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--base", help="last synchronized commit (checkpoint)")
    parser.add_argument("--target", required=True, help="upstream branch or commit, resolved explicitly")
    parser.add_argument("--find-equivalent", metavar="OLD_COMMIT")
    parser.add_argument("--limit", type=int, default=2000, help="commits to search with --find-equivalent")
    parser.add_argument("--output", help="write JSON here instead of stdout")
    args = parser.parse_args()
    if not args.find_equivalent and not args.base:
        parser.error("--base is required unless --find-equivalent is used")
    try:
        if args.find_equivalent:
            result = find_equivalent(args.repo, args.find_equivalent, args.target, args.limit)
        else:
            result = analyze(args.repo, args.base, args.target)
    except RuntimeError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        with open(args.output, "w") as handle:
            handle.write(text)
        print(json.dumps({"written": args.output, "status": result.get("status"),
                          "commits": len(result.get("commits", []))}))
    else:
        sys.stdout.write(text)
    return 0 if result.get("status") in ("ok", "no-new-commits", "candidates") else 3


if __name__ == "__main__":
    sys.exit(main())
