#!/usr/bin/env python3
"""Checkpoint, session and ledger store for sync-lovable-app.

State lives in <workspace>/.lovable-sync/ (see references/sync-state.md):

  sync-state.json        configuration, the single upstream checkpoint, history
  ledger.json            one record per upstream commit ever handled
  sessions/<id>.json     work units, conflicts and validations of one sync run
  reports/<id>.md        written by generate_report.py

Every mutating command takes a lock, writes files atomically (temp file + rename)
and commits the state directory to its own local Git history. The checkpoint only
moves through `finalize`, and only over upstream commits whose work units are
resolved, in repositories whose validations passed at their current HEAD.

Run `sync_state.py <command> --help` for each command. Requires Python 3.8+ and git.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid

SCHEMA_VERSION = 1
STATE_DIRNAME = ".lovable-sync"
REF_RELPATH = os.path.join(STATE_DIRNAME, "sync-ref.json")
ROLES = ("frontend", "backend")

UNIT_STATUSES = (
    "pending", "in-progress", "implemented", "verified", "already-present",
    "ignored", "declined", "retained-local", "deferred", "blocked",
)
# Statuses that let the checkpoint pass the unit's upstream commits.
RESOLVED = {"verified", "already-present", "ignored", "declined", "retained-local"}
CATEGORIES = (
    "feature", "ui", "bugfix", "validation", "api", "database", "auth", "storage",
    "realtime", "integration", "dependency", "configuration", "supabase-specific",
    "lovable-tooling", "docs", "tests", "revert", "other",
)
VALIDATION_RESULTS = ("PASS", "FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE")
VALIDATION_SCOPES = ROLES + ("integration",)
RESOLUTIONS = ("preserve", "adapt", "defer", "decline")


class SyncError(Exception):
    pass


# ---------------------------------------------------------------- helpers

def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def run_git(path, *args):
    return subprocess.run(["git", "-C", path, *args], capture_output=True, text=True)


def git(path, *args):
    result = run_git(path, *args)
    if result.returncode != 0:
        raise SyncError("git %s failed in %s: %s" % (" ".join(args), path, result.stderr.strip()))
    return result.stdout.strip()


def resolve_commit(path, ref):
    if not ref:
        return None
    result = run_git(path, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    return result.stdout.strip() if result.returncode == 0 else None


def is_ancestor(path, ancestor, descendant):
    return run_git(path, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def redact_url(url):
    return re.sub(r"^([a-zA-Z][\w+.-]*://)[^/@]+@", r"\1", url or "") or None


def is_git_repo(path):
    return os.path.isdir(path) and run_git(path, "rev-parse", "--git-dir").returncode == 0


def repo_identity(path):
    if not is_git_repo(path):
        raise SyncError("not a Git repository: %s" % path)
    roots = run_git(path, "rev-list", "--max-parents=0", "HEAD")
    remote = run_git(path, "remote", "get-url", "origin")
    if remote.returncode != 0:
        names = git(path, "remote").split()
        remote = run_git(path, "remote", "get-url", names[0]) if names else remote
    return {
        "rootCommits": sorted(roots.stdout.split()) if roots.returncode == 0 else [],
        "remoteUrl": redact_url(remote.stdout.strip()) if remote.returncode == 0 else None,
        "shallow": git(path, "rev-parse", "--is-shallow-repository") == "true",
    }


def dirty_entries(path):
    """Changed or untracked paths, ignoring the skill's own reference file."""
    out = run_git(path, "status", "--porcelain").stdout.splitlines()
    return [line for line in out if STATE_DIRNAME + "/" not in line]


def in_progress_operation(path):
    for marker in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
        rel = run_git(path, "rev-parse", "--git-path", marker).stdout.strip()
        if rel and os.path.exists(rel if os.path.isabs(rel) else os.path.join(path, rel)):
            return marker
    return None


def write_json(path, data):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as handle:
        return json.load(handle)


def emit(data):
    json.dump(data, sys.stdout, indent=2)
    sys.stdout.write("\n")


# ---------------------------------------------------------------- state store

class Store:
    def __init__(self, state_dir):
        self.dir = os.path.abspath(state_dir)
        self.workspace = os.path.dirname(self.dir)
        self.state_path = os.path.join(self.dir, "sync-state.json")
        self.ledger_path = os.path.join(self.dir, "ledger.json")
        self.lock_path = os.path.join(self.dir, ".lock")

    @classmethod
    def locate(cls, explicit):
        if explicit:
            candidate = os.path.abspath(explicit)
            if os.path.basename(candidate) != STATE_DIRNAME:
                candidate = os.path.join(candidate, STATE_DIRNAME)
            return cls(candidate)
        current = os.getcwd()
        while True:
            if os.path.exists(os.path.join(current, STATE_DIRNAME, "sync-state.json")):
                return cls(os.path.join(current, STATE_DIRNAME))
            parent = os.path.dirname(current)
            if parent == current:
                raise SyncError("no %s/sync-state.json found from the current directory upward; "
                                "pass --state-dir or run `init`" % STATE_DIRNAME)
            current = parent

    def state(self):
        state = read_json(self.state_path)
        if state is None:
            raise SyncError("sync state not initialized at %s; run `init`" % self.dir)
        if state.get("schemaVersion") != SCHEMA_VERSION:
            raise SyncError("unsupported schemaVersion %r" % state.get("schemaVersion"))
        return state

    def save_state(self, state):
        write_json(self.state_path, state)

    def ledger(self):
        return read_json(self.ledger_path, {"schemaVersion": SCHEMA_VERSION, "commits": {}})

    def session_path(self, session_id):
        if not re.match(r"^[\w.-]+$", session_id or ""):
            raise SyncError("invalid session id %r" % session_id)
        return os.path.join(self.dir, "sessions", session_id + ".json")

    def session(self, session_id):
        data = read_json(self.session_path(session_id))
        if data is None:
            raise SyncError("session %s not found" % session_id)
        return data

    def save_session(self, session):
        session["updatedAt"] = now()
        write_json(self.session_path(session["sessionId"]), session)

    def abs_path(self, rel):
        return os.path.normpath(os.path.join(self.workspace, rel))

    def rel_path(self, path):
        return os.path.relpath(os.path.abspath(path), self.workspace)

    def commit(self, message):
        if not is_git_repo(self.dir) or git(self.dir, "rev-parse", "--show-toplevel") != os.path.realpath(self.dir):
            return
        run_git(self.dir, "add", "-A")
        identity = []
        if run_git(self.dir, "config", "user.email").returncode != 0:
            identity = ["-c", "user.name=sync-lovable-app", "-c", "user.email=sync-lovable-app@localhost"]
        subprocess.run(["git", "-C", self.dir, *identity, "commit", "-q", "-m", message],
                       capture_output=True, text=True)


class Lock:
    def __init__(self, store):
        self.path = store.lock_path

    def __enter__(self):
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            with open(self.path) as handle:
                holder = handle.read().strip()
            raise SyncError("state is locked by another run (%s). If no sync is running, "
                            "release it with `sync_state.py unlock`." % holder)
        os.write(fd, json.dumps({"pid": os.getpid(), "at": now()}).encode())
        os.close(fd)
        return self

    def __exit__(self, *exc):
        if os.path.exists(self.path):
            os.unlink(self.path)


def repo_path(store, state, role):
    entry = state["source"] if role == "source" else state["targets"][role]
    return store.abs_path(entry["path"])


def work_location(store, state, session, role):
    """Path and branch where destination work for this session happens."""
    workspace = (session or {}).get("workspaces", {}).get(role)
    if workspace:
        return store.abs_path(workspace["path"]), workspace["branch"]
    entry = state["targets"][role]
    return store.abs_path(entry["path"]), entry["branch"]


def known_checkpoints(state):
    known = {entry["commit"] for entry in state.get("baselineHistory", [])}
    known.update(entry.get("checkpointAfter") for entry in state.get("history", []))
    known.add(state["source"]["lastSyncedCommit"])
    known.discard(None)
    return known


def active_session(store, state, explicit=None):
    session_id = explicit or state.get("activeSession")
    if not session_id:
        raise SyncError("no active session; start one with `start`")
    return store.session(session_id)


# ---------------------------------------------------------------- verification

def verify_checks(store, state):
    errors, warnings = [], []
    source = state["source"]
    roles = {"source": source}
    roles.update(state["targets"])
    for role, entry in roles.items():
        path = store.abs_path(entry["path"])
        if not is_git_repo(path):
            errors.append("%s repository missing or not a Git repository: %s" % (role, path))
            continue
        identity = repo_identity(path)
        if entry.get("rootCommits") and not set(identity["rootCommits"]) & set(entry["rootCommits"]):
            errors.append("%s repository at %s has different root commits than recorded; "
                          "it is not the same repository" % (role, path))
        if entry.get("remoteUrl") and identity["remoteUrl"] and identity["remoteUrl"] != entry["remoteUrl"]:
            warnings.append("%s remote URL changed from %s to %s" % (role, entry["remoteUrl"], identity["remoteUrl"]))
        if identity["shallow"]:
            warnings.append("%s is a shallow clone; history checks may be incomplete" % role)
        if resolve_commit(path, entry["branch"]) is None:
            errors.append("%s branch %s does not resolve" % (role, entry["branch"]))
        operation = in_progress_operation(path)
        if operation:
            errors.append("%s has an unfinished Git operation (%s); finish or abort it manually" % (role, operation))

    source_path = store.abs_path(source["path"])
    if is_git_repo(source_path):
        checkpoint = source["lastSyncedCommit"]
        tip = resolve_commit(source_path, source["branch"])
        if resolve_commit(source_path, checkpoint) is None:
            errors.append("checkpoint %s does not exist in the source repository "
                          "(shallow clone, unfetched history or rewritten branch)" % checkpoint[:12])
        elif tip and not is_ancestor(source_path, checkpoint, tip):
            errors.append("checkpoint %s is not an ancestor of %s: upstream history was rewritten; "
                          "run analyze_commits.py --find-equivalent and ask the user before `rebaseline`"
                          % (checkpoint[:12], source["branch"]))

    session = None
    if state.get("activeSession"):
        try:
            session = store.session(state["activeSession"])
        except SyncError as exc:
            errors.append(str(exc))

    for role in ROLES:
        entry = state["targets"][role]
        path = store.abs_path(entry["path"])
        if not is_git_repo(path):
            continue
        validated = entry.get("lastValidatedCommit")
        if validated and resolve_commit(path, validated) is None:
            errors.append("%s lastValidatedCommit %s no longer exists" % (role, validated[:12]))
        elif validated:
            tip = resolve_commit(path, entry["branch"])
            if tip and not is_ancestor(path, validated, tip):
                warnings.append("%s validated commit %s is not merged into %s (work branch: %s)"
                                % (role, validated[:12], entry["branch"], entry.get("workBranch")))
        work_path, _ = work_location(store, state, session, role)
        if dirty_entries(work_path):
            warnings.append("%s has uncommitted changes in %s" % (role, work_path))
        ref = read_json(os.path.join(work_path, REF_RELPATH))
        if ref:
            if ref.get("stateId") != state["stateId"]:
                errors.append("%s sync-ref.json belongs to a different sync state (%s)" % (role, ref.get("stateId")))
            elif ref.get("lastSyncedCommit") not in known_checkpoints(state):
                errors.append("%s sync-ref.json records checkpoint %s that the canonical state never "
                              "reached; the canonical state may be stale or lost" % (role, ref.get("lastSyncedCommit")))
            elif ref.get("lastSyncedCommit") != source["lastSyncedCommit"]:
                warnings.append("%s sync-ref.json lags the canonical checkpoint (branch not merged yet?)" % role)
    return errors, warnings


# ---------------------------------------------------------------- progress computation

def same_code(path, validated_head, current_head):
    """True when nothing but the skill's own reference file changed since validation."""
    if not validated_head or not current_head:
        return False
    if validated_head == current_head:
        return True
    if not is_ancestor(path, validated_head, current_head):
        return False
    changed = git(path, "diff", "--name-only", validated_head, current_head).splitlines()
    return all(name.startswith(STATE_DIRNAME + "/") for name in changed)


def compute_progress(store, state, session):
    """Derive commit resolution, validation problems and the advanceable checkpoint."""
    source_path = repo_path(store, state, "source")
    units = session["units"]
    open_conflicts = {c.get("unit") for c in session["conflicts"] if c["status"] != "resolved"}
    heads, problems = {}, []

    for role in ROLES:
        path, branch = work_location(store, state, session, role)
        heads[role] = {"path": store.rel_path(path), "branch": branch, "head": resolve_commit(path, "HEAD")}

    touched = set()
    for unit in units:
        if unit["status"] != "verified":
            continue
        for role in ROLES:
            for commit in unit[role + "Commits"]:
                touched.add(role)
                head = heads[role]["head"]
                if not head or not is_ancestor(store.abs_path(heads[role]["path"]), commit, head):
                    problems.append("unit %s: %s commit %s is not on the current %s work branch"
                                    % (unit["id"], role, commit[:12], role))

    for scope in sorted(touched) + ["integration"]:
        checks = [v for v in session["validations"] if v["scope"] == scope]
        for check in checks:
            if check["result"] in ("FAIL", "BLOCKED", "NOT_RUN"):
                problems.append("validation %s/%s is %s" % (scope, check["name"], check["result"]))
            if scope in ROLES and not same_code(store.abs_path(heads[scope]["path"]), check.get("head"),
                                                heads[scope]["head"]):
                problems.append("validation %s/%s ran at %s but the work branch is now at %s; rerun it"
                                % (scope, check["name"], (check.get("head") or "?")[:12],
                                   (heads[scope]["head"] or "?")[:12]))
            if scope == "integration":
                for role in ROLES:
                    if not same_code(store.abs_path(heads[role]["path"]), check.get("heads", {}).get(role),
                                     heads[role]["head"]):
                        problems.append("validation integration/%s ran before the latest %s changes; rerun it"
                                        % (check["name"], role))
            if check.get("dirty"):
                problems.append("validation %s/%s ran with uncommitted changes; commit and rerun it"
                                % (scope, check["name"]))
        if scope in ROLES and not any(c["result"] == "PASS" for c in checks):
            problems.append("no passing validation recorded for %s" % scope)
    both = any(unit["status"] == "verified" and unit["frontendCommits"] and unit["backendCommits"]
               for unit in units)
    if both and not any(v["scope"] == "integration" and v["result"] == "PASS" for v in session["validations"]):
        problems.append("units changed both repositories but no passing integration validation is recorded")

    commit_status = {}
    for entry in session["commits"]:
        covering = [u for u in units if entry["hash"] in u["commits"]]
        if covering:
            resolved = all(u["status"] in RESOLVED and u["id"] not in open_conflicts for u in covering)
            waiting = [u["id"] for u in covering if u["status"] not in RESOLVED or u["id"] in open_conflicts]
        else:
            resolved = bool(entry.get("previouslyResolved"))
            waiting = [] if resolved else ["(no work unit)"]
        commit_status[entry["hash"]] = {"resolved": resolved, "waitingOn": waiting,
                                        "units": [u["id"] for u in covering]}

    checkpoint = session["startCommit"]
    if not problems:
        resolved_set = {h for h, s in commit_status.items() if s["resolved"]}
        for entry in reversed(session["commits"]):
            if entry["hash"] not in resolved_set:
                continue
            needed = git(source_path, "rev-list", "%s..%s" % (session["startCommit"], entry["hash"])).split()
            if set(needed) <= resolved_set:
                checkpoint = entry["hash"]
                break

    return {
        "heads": heads,
        "touched": sorted(touched),
        "problems": problems,
        "commits": commit_status,
        "unresolvedCommits": [h for h, s in commit_status.items() if not s["resolved"]],
        "openConflicts": sorted(c for c in open_conflicts if c),
        "checkpointAfter": checkpoint,
        "reachesTarget": checkpoint == session["targetCommit"],
    }


def dispositions(units):
    if not units:
        return ["previously-resolved"]
    result = set()
    for unit in units:
        if unit["status"] == "verified":
            if unit["frontendCommits"] and unit["backendCommits"]:
                result.add("both")
            elif unit["frontendCommits"]:
                result.add("frontend")
            elif unit["backendCommits"]:
                result.add("backend")
        else:
            result.add(unit["status"])
    return sorted(result)


# ---------------------------------------------------------------- commands

def cmd_init(args):
    workspace = os.path.abspath(args.workspace)
    store = Store(os.path.join(workspace, STATE_DIRNAME))
    if os.path.exists(store.state_path):
        raise SyncError("already initialized at %s" % store.dir)
    paths = {"source": args.source, "frontend": args.frontend, "backend": args.backend}
    branches = {"source": args.source_branch, "frontend": args.frontend_branch, "backend": args.backend_branch}
    entries = {}
    for role, path in paths.items():
        path = os.path.abspath(path)
        identity = repo_identity(path)
        tip = resolve_commit(path, branches[role])
        if tip is None:
            raise SyncError("%s branch %r does not resolve in %s" % (role, branches[role], path))
        entries[role] = {"path": store.rel_path(path), "branch": branches[role],
                         "remoteUrl": identity["remoteUrl"], "rootCommits": identity["rootCommits"],
                         "tip": tip, "shallow": identity["shallow"]}
    for role in ROLES:
        if entries[role]["path"] == entries["source"]["path"] and entries[role]["branch"] == entries["source"]["branch"]:
            raise SyncError("%s and source are the same repository and branch" % role)
    source_path = store.abs_path(entries["source"]["path"])
    baseline = resolve_commit(source_path, args.baseline)
    if baseline is None:
        raise SyncError("baseline %r not found in the source repository (shallow clone or unfetched "
                        "history? ask the user before fetching)" % args.baseline)
    if not is_ancestor(source_path, baseline, entries["source"]["tip"]):
        raise SyncError("baseline %s is not an ancestor of %s" % (baseline[:12], args.source_branch))

    state = {
        "schemaVersion": SCHEMA_VERSION,
        "stateId": str(uuid.uuid4()),
        "createdAt": now(),
        "source": {
            "path": entries["source"]["path"], "branch": args.source_branch,
            "remoteUrl": entries["source"]["remoteUrl"], "rootCommits": entries["source"]["rootCommits"],
            "allowFetch": args.allow_fetch, "lastSyncedCommit": baseline,
        },
        "targets": {
            role: {
                "path": entries[role]["path"], "branch": branches[role],
                "remoteUrl": entries[role]["remoteUrl"], "rootCommits": entries[role]["rootCommits"],
                "lastValidatedCommit": entries[role]["tip"], "workBranch": None,
            } for role in ROLES
        },
        "lastSuccessfulSync": {"sessionId": None, "sourceCommit": baseline, "completedAt": now(),
                               "status": "baseline"},
        "activeSession": None,
        "history": [],
        "baselineHistory": [{"commit": baseline, "previous": None, "setAt": now(),
                             "reason": args.reason, "approvedByUser": True}],
    }
    os.makedirs(os.path.join(store.dir, "sessions"), exist_ok=True)
    with open(os.path.join(store.dir, ".gitignore"), "w") as handle:
        handle.write(".lock\n.tmp-*\nworktrees/\n")
    store.save_state(state)
    write_json(store.ledger_path, store.ledger())
    if not is_git_repo(store.dir) or git(store.dir, "rev-parse", "--show-toplevel") != os.path.realpath(store.dir):
        git(store.dir, "init", "-q")
    store.commit("init: baseline %s" % baseline[:12])
    emit({"initialized": store.dir, "baseline": baseline,
          "shallow": [r for r, e in entries.items() if e["shallow"]]})


def cmd_status(args):
    store = Store.locate(args.state_dir)
    state = store.state()
    errors, warnings = verify_checks(store, state)
    source = state["source"]
    source_path = repo_path(store, state, "source")
    tip = resolve_commit(source_path, source["branch"])
    checkpoint = source["lastSyncedCommit"]
    pending = None
    if tip and resolve_commit(source_path, checkpoint) and is_ancestor(source_path, checkpoint, tip):
        pending = int(git(source_path, "rev-list", "--count", "%s..%s" % (checkpoint, tip)))
    tracking = None
    upstream = run_git(source_path, "rev-parse", "--abbrev-ref", source["branch"] + "@{upstream}")
    if upstream.returncode == 0:
        counts = run_git(source_path, "rev-list", "--left-right", "--count",
                         "%s...%s" % (upstream.stdout.strip(), source["branch"])).stdout.split()
        if len(counts) == 2:
            tracking = {"remoteRef": upstream.stdout.strip(), "behindRemote": int(counts[0]),
                        "aheadOfRemote": int(counts[1])}
    repos = {}
    for role in ("source",) + ROLES:
        path = repo_path(store, state, role)
        if is_git_repo(path):
            repos[role] = {"path": path, "currentBranch": git(path, "branch", "--show-current") or "(detached)",
                           "head": resolve_commit(path, "HEAD"), "uncommittedEntries": len(dirty_entries(path))}
    session_summary = None
    if state.get("activeSession") and not errors:
        session = store.session(state["activeSession"])
        progress = compute_progress(store, state, session)
        by_status = {}
        for unit in session["units"]:
            by_status[unit["status"]] = by_status.get(unit["status"], 0) + 1
        session_summary = {"sessionId": session["sessionId"], "status": session["status"],
                           "targetCommit": session["targetCommit"], "units": by_status,
                           "unresolvedCommits": len(progress["unresolvedCommits"]),
                           "openConflicts": progress["openConflicts"], "problems": progress["problems"]}
    emit({
        "stateDir": store.dir,
        "source": {"branch": source["branch"], "branchTip": tip, "tracking": tracking},
        "lastSuccessfulSync": state["lastSuccessfulSync"],
        "checkpoint": checkpoint,
        "pendingCommits": pending,
        "targets": {r: {k: state["targets"][r].get(k) for k in ("branch", "lastValidatedCommit", "workBranch")}
                    for r in ROLES},
        "repositories": repos,
        "activeSession": session_summary,
        "errors": errors,
        "warnings": warnings,
    })
    return 1 if errors else 0


def cmd_verify(args):
    store = Store.locate(args.state_dir)
    errors, warnings = verify_checks(store, store.state())
    emit({"ok": not errors, "errors": errors, "warnings": warnings})
    return 1 if errors else 0


def cmd_start(args):
    store = Store.locate(args.state_dir)
    with Lock(store):
        state = store.state()
        if state.get("activeSession"):
            raise SyncError("session %s is still active; use `resume` or `close` it first" % state["activeSession"])
        errors, _ = verify_checks(store, state)
        if errors:
            raise SyncError("preflight failed:\n- " + "\n- ".join(errors))
        source_path = repo_path(store, state, "source")
        base = state["source"]["lastSyncedCommit"]
        target = resolve_commit(source_path, args.target or state["source"]["branch"])
        if target is None:
            raise SyncError("target %r does not resolve" % (args.target or state["source"]["branch"]))
        if target == base:
            emit({"newCommits": 0, "message": "already synchronized at %s" % base[:12]})
            return 0
        if not is_ancestor(source_path, base, target):
            raise SyncError("checkpoint %s is not an ancestor of %s" % (base[:12], target[:12]))
        hashes = git(source_path, "rev-list", "--topo-order", "--reverse", "%s..%s" % (base, target)).split()
        ledger = store.ledger()["commits"]
        commits = []
        for commit in hashes:
            entry = {"hash": commit, "subject": git(source_path, "log", "-1", "--format=%s", commit)}
            record = ledger.get(commit)
            if record and record.get("resolved"):
                merged = all(
                    resolve_commit(store.abs_path(state["targets"][role]["path"]), c) and
                    is_ancestor(store.abs_path(state["targets"][role]["path"]), c,
                                resolve_commit(store.abs_path(state["targets"][role]["path"]),
                                               state["targets"][role]["branch"]))
                    for role in ROLES for c in record.get(role + "Commits", []))
                entry["previouslyResolved"] = merged
                entry["previousSession"] = record.get("sessionId")
            commits.append(entry)
        session_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        session = {
            "schemaVersion": SCHEMA_VERSION, "sessionId": session_id, "status": "in-progress",
            "startedAt": now(), "updatedAt": now(), "endedAt": None,
            "sourceBranch": state["source"]["branch"], "startCommit": base, "targetCommit": target,
            "commits": commits, "units": [], "conflicts": [], "validations": [], "workspaces": {},
            "result": None, "events": [{"at": now(), "event": "started"}],
        }
        store.save_session(session)
        state["activeSession"] = session_id
        store.save_state(state)
        store.commit("start %s: %s..%s" % (session_id, base[:12], target[:12]))
        emit({"sessionId": session_id, "startCommit": base, "targetCommit": target, "newCommits": len(commits),
              "previouslyResolved": [c["hash"] for c in commits if c.get("previouslyResolved")]})
    return 0


def cmd_workspace(args):
    store = Store.locate(args.state_dir)
    with Lock(store):
        state = store.state()
        session = active_session(store, state, args.session)
        path = os.path.abspath(args.path)
        identity = repo_identity(path)
        if not set(identity["rootCommits"]) & set(state["targets"][args.role]["rootCommits"]):
            raise SyncError("%s is not a checkout of the %s repository" % (path, args.role))
        current = git(path, "branch", "--show-current")
        if current != args.branch:
            raise SyncError("%s is on branch %r, expected %r" % (path, current, args.branch))
        session["workspaces"][args.role] = {"path": store.rel_path(path), "branch": args.branch,
                                            "baseCommit": resolve_commit(path, "HEAD")}
        session["events"].append({"at": now(), "event": "workspace %s -> %s@%s" % (args.role, path, args.branch)})
        store.save_session(session)
        store.commit("%s: %s workspace %s" % (session["sessionId"], args.role, args.branch))
        emit(session["workspaces"][args.role])


def split_values(values):
    result = []
    for value in values or []:
        result.extend(v.strip() for v in value.split(",") if v.strip())
    return result


def cmd_unit(args):
    store = Store.locate(args.state_dir)
    with Lock(store):
        state = store.state()
        session = active_session(store, state, args.session)
        source_path = repo_path(store, state, "source")
        session_hashes = {c["hash"] for c in session["commits"]}
        unit = next((u for u in session["units"] if u["id"] == args.id), None)
        if unit is None:
            unit = {"id": args.id, "title": "", "intent": "", "category": None, "commits": [],
                    "targets": [], "status": "pending", "frontendCommits": [], "backendCommits": [],
                    "evidence": [], "reason": None, "decision": None, "userApproved": False}
            session["units"].append(unit)
        for field in ("title", "intent", "category", "reason", "decision"):
            value = getattr(args, field)
            if value is not None:
                unit[field] = value
        if args.targets is not None:
            unit["targets"] = [t for t in split_values([args.targets]) if t in ROLES]
        for ref in split_values(args.commit):
            full = resolve_commit(source_path, ref)
            if full not in session_hashes:
                raise SyncError("upstream commit %s is not part of session %s" % (ref, session["sessionId"]))
            if full not in unit["commits"]:
                unit["commits"].append(full)
        for role in ROLES:
            path, _ = work_location(store, state, session, role)
            for ref in split_values(getattr(args, role + "_commit")):
                full = resolve_commit(path, ref)
                if full is None:
                    raise SyncError("%s commit %s not found in %s" % (role, ref, path))
                if full not in unit[role + "Commits"]:
                    unit[role + "Commits"].append(full)
        unit["evidence"].extend(args.evidence or [])
        if args.user_approved:
            unit["userApproved"] = True
        if args.status:
            status = args.status
            if not unit["commits"]:
                raise SyncError("unit %s covers no upstream commits; add --commit" % unit["id"])
            if status == "verified":
                for role in unit["targets"]:
                    if not unit[role + "Commits"]:
                        raise SyncError("verified unit targets %s but records no %s commits" % (role, role))
                if not unit["targets"]:
                    raise SyncError("verified unit needs --targets")
                if not unit["evidence"]:
                    raise SyncError("verified unit needs --evidence (tests or checks that prove the behavior)")
            if status == "already-present" and not unit["evidence"]:
                raise SyncError("already-present needs --evidence naming where and how the behavior was compared")
            if status in ("ignored", "deferred", "blocked") and not unit["reason"]:
                raise SyncError("%s needs --reason" % status)
            if status in ("declined", "retained-local") and not (unit["decision"] and unit["userApproved"]):
                raise SyncError("%s needs --decision and --user-approved (the user must decide)" % status)
            unit["status"] = status
        unit["updatedAt"] = now()
        if unit["category"] and unit["category"] not in CATEGORIES:
            raise SyncError("unknown category %r; use one of %s" % (unit["category"], ", ".join(CATEGORIES)))
        session["events"].append({"at": now(), "event": "unit %s -> %s" % (unit["id"], unit["status"])})
        store.save_session(session)
        store.commit("%s: unit %s %s" % (session["sessionId"], unit["id"], unit["status"]))
        emit(unit)


def cmd_conflict(args):
    store = Store.locate(args.state_dir)
    with Lock(store):
        state = store.state()
        session = active_session(store, state, args.session)
        conflict = next((c for c in session["conflicts"] if c["id"] == args.id), None)
        if conflict is None:
            conflict = {"id": args.id, "unit": None, "feature": "", "upstreamChange": "", "existing": "",
                        "reason": "", "proposal": "", "impact": "", "needsApproval": True,
                        "resolution": None, "userApproved": False, "status": "open"}
            session["conflicts"].append(conflict)
        mapping = {"unit": "unit", "feature": "feature", "upstream_change": "upstreamChange",
                   "existing": "existing", "reason": "reason", "proposal": "proposal", "impact": "impact",
                   "resolution": "resolution"}
        for arg, field in mapping.items():
            value = getattr(args, arg)
            if value is not None:
                conflict[field] = value
        if args.needs_approval is not None:
            conflict["needsApproval"] = args.needs_approval == "yes"
        if args.user_approved:
            conflict["userApproved"] = True
        if args.status == "resolved":
            if not conflict["resolution"]:
                raise SyncError("resolving a conflict needs --resolution")
            if conflict["needsApproval"] and not conflict["userApproved"]:
                raise SyncError("this conflict needs the user's approval (--user-approved) before it is resolved")
        if args.status:
            conflict["status"] = args.status
        session["events"].append({"at": now(), "event": "conflict %s -> %s" % (conflict["id"], conflict["status"])})
        store.save_session(session)
        store.commit("%s: conflict %s %s" % (session["sessionId"], conflict["id"], conflict["status"]))
        emit(conflict)


def cmd_validation(args):
    store = Store.locate(args.state_dir)
    with Lock(store):
        state = store.state()
        session = active_session(store, state, args.session)
        record = {"scope": args.scope, "name": args.name, "command": args.command, "result": args.result,
                  "evidence": args.evidence, "at": now()}
        if args.scope in ROLES:
            path, _ = work_location(store, state, session, args.scope)
            record["head"] = resolve_commit(path, "HEAD")
            record["dirty"] = bool(dirty_entries(path))
        else:
            record["heads"], record["dirty"] = {}, False
            for role in ROLES:
                path, _ = work_location(store, state, session, role)
                record["heads"][role] = resolve_commit(path, "HEAD")
                record["dirty"] = record["dirty"] or bool(dirty_entries(path))
        session["validations"] = [v for v in session["validations"]
                                  if not (v["scope"] == args.scope and v["name"] == args.name)]
        session["validations"].append(record)
        session["events"].append({"at": now(), "event": "validation %s/%s %s" % (args.scope, args.name, args.result)})
        store.save_session(session)
        store.commit("%s: validation %s/%s %s" % (session["sessionId"], args.scope, args.name, args.result))
        emit(record)


def cmd_resume(args):
    store = Store.locate(args.state_dir)
    state = store.state()
    session = active_session(store, state, args.session)
    progress = compute_progress(store, state, session)
    covered = {h for u in session["units"] for h in u["commits"]}
    emit({
        "sessionId": session["sessionId"],
        "status": session["status"],
        "range": [session["startCommit"], session["targetCommit"]],
        "workspaces": session["workspaces"],
        "uncoveredCommits": [c for c in session["commits"]
                             if c["hash"] not in covered and not c.get("previouslyResolved")],
        "unitsNotResolved": [{"id": u["id"], "title": u["title"], "status": u["status"], "reason": u["reason"]}
                             for u in session["units"] if u["status"] not in RESOLVED],
        "openConflicts": [c for c in session["conflicts"] if c["status"] != "resolved"],
        "problems": progress["problems"],
        "checkpointIfFinalizedNow": progress["checkpointAfter"],
        "reachesTarget": progress["reachesTarget"],
    })


def write_refs(store, state, session, checkpoint, progress):
    written = []
    for role in ROLES:
        path, branch = work_location(store, state, session, role)
        ref_path = os.path.join(path, REF_RELPATH)
        ref = read_json(ref_path, {"schemaVersion": SCHEMA_VERSION, "stateId": state["stateId"],
                                   "role": role, "sessions": []})
        unit_ids = [u["id"] for u in session["units"] if u[role + "Commits"]]
        if role not in progress["touched"] and not os.path.exists(ref_path):
            continue
        ref["lastSyncedCommit"] = checkpoint
        ref["lastSessionId"] = session["sessionId"]
        ref["sessions"] = [s for s in ref["sessions"] if s["sessionId"] != session["sessionId"]]
        # Checkpoint range of the canonical state, plus every unit applied in this repo so
        # far (applied units may lie beyond the checkpoint while the session is partial).
        ref["sessions"].append({
            "sessionId": session["sessionId"], "status": session["status"],
            "checkpointRange": [session["startCommit"], checkpoint],
            "appliedUnits": unit_ids,
            "appliedUpstreamCommits": sorted({h for u in session["units"] if u[role + "Commits"] for h in u["commits"]}),
            "destinationCommits": sorted({c for u in session["units"] for c in u[role + "Commits"]}),
        })
        write_json(ref_path, ref)
        written.append(ref_path)
    return written


def cmd_finalize(args):
    store = Store.locate(args.state_dir)
    with Lock(store):
        state = store.state()
        session = active_session(store, state, args.session)
        progress = compute_progress(store, state, session)
        base = session["startCommit"]
        current = state["source"]["lastSyncedCommit"]
        checkpoint = progress["checkpointAfter"]
        # An earlier finalize of this session may already have moved the checkpoint;
        # never move it backwards because of a later problem.
        if checkpoint != current and is_ancestor(repo_path(store, state, "source"), checkpoint, current):
            checkpoint = current
        if args.dry_run:
            progress["checkpointAfter"] = checkpoint
            emit(progress)
            return 0

        if checkpoint == session["targetCommit"]:
            status = "completed"
        elif checkpoint != base:
            status = "partial"
        else:
            status = "in-progress"
        session["status"] = status
        session["result"] = {"at": now(), "checkpointAfter": checkpoint, "problems": progress["problems"],
                             "unresolvedCommits": progress["unresolvedCommits"],
                             "openConflicts": progress["openConflicts"], "heads": progress["heads"]}
        if status == "completed":
            session["endedAt"] = now()
        session["events"].append({"at": now(), "event": "finalize -> %s at %s" % (status, checkpoint[:12])})
        store.save_session(session)

        ledger = store.ledger()
        for entry in session["commits"]:
            info = progress["commits"][entry["hash"]]
            covering = [u for u in session["units"] if entry["hash"] in u["commits"]]
            ledger["commits"][entry["hash"]] = {
                "subject": entry["subject"], "sessionId": session["sessionId"], "resolved": info["resolved"],
                "dispositions": dispositions(covering) if info["resolved"] or covering else ["pending"],
                "units": info["units"], "waitingOn": info["waitingOn"],
                "frontendCommits": sorted({c for u in covering for c in u["frontendCommits"]}),
                "backendCommits": sorted({c for u in covering for c in u["backendCommits"]}),
                "recordedAt": now(),
            }
        write_json(store.ledger_path, ledger)

        advanced = checkpoint != current
        if advanced:
            state["source"]["lastSyncedCommit"] = checkpoint
            state["lastSuccessfulSync"] = {"sessionId": session["sessionId"], "sourceCommit": checkpoint,
                                           "completedAt": now(), "status": status}
            for role in progress["touched"]:
                state["targets"][role]["lastValidatedCommit"] = progress["heads"][role]["head"]
                state["targets"][role]["workBranch"] = progress["heads"][role]["branch"]
        history = [h for h in state["history"] if h["sessionId"] != session["sessionId"]]
        history.append({"sessionId": session["sessionId"], "status": status, "startCommit": base,
                        "targetCommit": session["targetCommit"], "checkpointAfter": state["source"]["lastSyncedCommit"],
                        "startedAt": session["startedAt"], "endedAt": session["endedAt"],
                        "destinationHeads": {r: progress["heads"][r]["head"] for r in progress["touched"]}})
        state["history"] = history
        if status == "completed":
            state["activeSession"] = None
        store.save_state(state)
        refs = write_refs(store, state, session, state["source"]["lastSyncedCommit"], progress) if advanced else []
        store.commit("%s: finalize %s, checkpoint %s" % (session["sessionId"], status,
                                                         state["source"]["lastSyncedCommit"][:12]))
        emit({"sessionId": session["sessionId"], "status": status, "checkpointAdvanced": advanced,
              "checkpoint": state["source"]["lastSyncedCommit"], "problems": progress["problems"],
              "unresolvedCommits": progress["unresolvedCommits"], "openConflicts": progress["openConflicts"],
              "refsWritten": refs,
              "next": "commit the sync-ref.json files in their repositories" if refs else None})
    return 0 if status == "completed" else 2


def cmd_close(args):
    store = Store.locate(args.state_dir)
    with Lock(store):
        state = store.state()
        session = active_session(store, state, args.session)
        session["status"] = "abandoned"
        session["endedAt"] = now()
        session["events"].append({"at": now(), "event": "closed: %s" % args.reason})
        store.save_session(session)
        state["activeSession"] = None
        history = [h for h in state["history"] if h["sessionId"] != session["sessionId"]]
        history.append({"sessionId": session["sessionId"], "status": "abandoned",
                        "startCommit": session["startCommit"], "targetCommit": session["targetCommit"],
                        "checkpointAfter": state["source"]["lastSyncedCommit"], "startedAt": session["startedAt"],
                        "endedAt": session["endedAt"], "reason": args.reason})
        state["history"] = history
        store.save_state(state)
        store.commit("%s: closed (%s)" % (session["sessionId"], args.reason))
        emit({"sessionId": session["sessionId"], "status": "abandoned",
              "checkpoint": state["source"]["lastSyncedCommit"]})


def cmd_rebaseline(args):
    if not args.user_approved:
        raise SyncError("changing the baseline needs the user's explicit approval (--user-approved)")
    store = Store.locate(args.state_dir)
    with Lock(store):
        state = store.state()
        if state.get("activeSession"):
            raise SyncError("close the active session before changing the baseline")
        source_path = repo_path(store, state, "source")
        commit = resolve_commit(source_path, args.commit)
        tip = resolve_commit(source_path, state["source"]["branch"])
        if commit is None or not is_ancestor(source_path, commit, tip):
            raise SyncError("%s is not a commit on %s" % (args.commit, state["source"]["branch"]))
        previous = state["source"]["lastSyncedCommit"]
        state["source"]["lastSyncedCommit"] = commit
        state["baselineHistory"].append({"commit": commit, "previous": previous, "setAt": now(),
                                         "reason": args.reason, "evidence": args.evidence,
                                         "approvedByUser": True})
        state["lastSuccessfulSync"] = {"sessionId": None, "sourceCommit": commit, "completedAt": now(),
                                       "status": "rebaselined"}
        store.save_state(state)
        store.commit("rebaseline %s -> %s: %s" % (previous[:12], commit[:12], args.reason))
        emit({"previous": previous, "checkpoint": commit})


def cmd_history(args):
    store = Store.locate(args.state_dir)
    state = store.state()
    emit({"sessions": state["history"][-args.limit:], "baselines": state["baselineHistory"],
          "lastSuccessfulSync": state["lastSuccessfulSync"]})


def cmd_show(args):
    store = Store.locate(args.state_dir)
    state = store.state()
    if args.session:
        emit(store.session(args.session))
    elif args.commit:
        source_path = repo_path(store, state, "source")
        full = resolve_commit(source_path, args.commit) or args.commit
        emit(store.ledger()["commits"].get(full) or {"commit": full, "recorded": False})
    else:
        emit(state)


def cmd_unlock(args):
    store = Store.locate(args.state_dir)
    if os.path.exists(store.lock_path):
        os.unlink(store.lock_path)
        emit({"unlocked": True})
    else:
        emit({"unlocked": False, "message": "no lock present"})


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state-dir", help="workspace or .lovable-sync directory (default: search upward)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create the sync state from a confirmed baseline")
    p.add_argument("--workspace", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--source-branch", required=True)
    p.add_argument("--frontend", required=True)
    p.add_argument("--frontend-branch", required=True)
    p.add_argument("--backend", required=True)
    p.add_argument("--backend-branch", required=True)
    p.add_argument("--baseline", required=True, help="last upstream commit the migrated apps already contain")
    p.add_argument("--reason", required=True, help="how the user confirmed the baseline")
    p.add_argument("--allow-fetch", action="store_true", help="the user allowed `git fetch` in the source repo")
    p.set_defaults(func=cmd_init)

    sub.add_parser("status", help="checkpoint, pending commits, repositories, active session").set_defaults(func=cmd_status)
    sub.add_parser("verify", help="consistency checks only").set_defaults(func=cmd_verify)

    p = sub.add_parser("start", help="open a session from the checkpoint to a target revision")
    p.add_argument("--target", help="upstream ref or commit (default: the configured source branch)")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("workspace", help="record where a destination's work happens (branch or worktree)")
    p.add_argument("--session")
    p.add_argument("--role", choices=ROLES, required=True)
    p.add_argument("--path", required=True)
    p.add_argument("--branch", required=True)
    p.set_defaults(func=cmd_workspace)

    p = sub.add_parser("unit", help="create or update a work unit")
    p.add_argument("--session")
    p.add_argument("--id", required=True)
    p.add_argument("--title")
    p.add_argument("--intent", help="functional requirement in one or two sentences")
    p.add_argument("--category")
    p.add_argument("--commit", action="append", help="upstream commit(s) covered (repeatable, comma-separated)")
    p.add_argument("--targets", help="frontend, backend or frontend,backend")
    p.add_argument("--frontend-commit", action="append")
    p.add_argument("--backend-commit", action="append")
    p.add_argument("--evidence", action="append")
    p.add_argument("--reason")
    p.add_argument("--decision")
    p.add_argument("--user-approved", action="store_true")
    p.add_argument("--status", choices=UNIT_STATUSES)
    p.set_defaults(func=cmd_unit)

    p = sub.add_parser("conflict", help="create or update a semantic conflict")
    p.add_argument("--session")
    p.add_argument("--id", required=True)
    p.add_argument("--unit")
    p.add_argument("--feature")
    p.add_argument("--upstream-change")
    p.add_argument("--existing")
    p.add_argument("--reason")
    p.add_argument("--proposal")
    p.add_argument("--impact")
    p.add_argument("--needs-approval", choices=("yes", "no"))
    p.add_argument("--resolution", choices=RESOLUTIONS)
    p.add_argument("--user-approved", action="store_true")
    p.add_argument("--status", choices=("open", "resolved"))
    p.set_defaults(func=cmd_conflict)

    p = sub.add_parser("validation", help="record a check result at the current work HEAD")
    p.add_argument("--session")
    p.add_argument("--scope", choices=VALIDATION_SCOPES, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--command", required=True)
    p.add_argument("--result", choices=VALIDATION_RESULTS, required=True)
    p.add_argument("--evidence", required=True, help="short outcome summary, never secret values")
    p.set_defaults(func=cmd_validation)

    p = sub.add_parser("resume", help="what remains in the active session")
    p.add_argument("--session")
    p.set_defaults(func=cmd_resume)

    p = sub.add_parser("finalize", help="advance the checkpoint over verified work")
    p.add_argument("--session")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_finalize)

    p = sub.add_parser("close", help="end the active session without moving the checkpoint")
    p.add_argument("--session")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_close)

    p = sub.add_parser("rebaseline", help="set a new checkpoint after rewritten history (user-approved)")
    p.add_argument("--commit", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--evidence", help="how the new commit was mapped (patch-id, subjects, review)")
    p.add_argument("--user-approved", action="store_true")
    p.set_defaults(func=cmd_rebaseline)

    p = sub.add_parser("history", help="past sessions and baselines")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("show", help="print the state, a session or a ledger record")
    p.add_argument("--session")
    p.add_argument("--commit", help="upstream commit to look up in the ledger")
    p.set_defaults(func=cmd_show)

    sub.add_parser("unlock", help="remove a stale lock after a crashed run").set_defaults(func=cmd_unlock)
    return parser


def main():
    args = build_parser().parse_args()
    try:
        return args.func(args) or 0
    except SyncError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
