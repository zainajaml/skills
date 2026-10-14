#!/usr/bin/env python3
"""Find Git repositories under a workspace and describe them for role confirmation.

Usage: discover_repositories.py <workspace> [--depth 2]

Read-only. Prints JSON with, per repository: branch, HEAD, uncommitted entry
counts, unfinished Git operations, remotes (credentials stripped), shallow flag,
root commits, detected frameworks, Lovable/Supabase/migration signals and role
hints. Role hints are evidence to show the user; the user confirms every role.
Also reports an existing <workspace>/.lovable-sync state. Requires Python 3.8+ and git.
"""
import argparse
import json
import os
import re
import subprocess
import sys

SKIP_DIRS = {"node_modules", "dist", "build", ".next", ".nuxt", ".output", "vendor", ".venv", "coverage",
             ".lovable-sync"}


def git(path, *args):
    result = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def redact(url):
    return re.sub(r"^([a-zA-Z][\w+.-]*://)[^/@]+@", r"\1", url)


def find_repos(root, depth):
    found = []

    def walk(path, remaining):
        if os.path.exists(os.path.join(path, ".git")):
            found.append(path)
            return
        if remaining == 0:
            return
        try:
            entries = sorted(os.scandir(path), key=lambda e: e.name)
        except OSError:
            return
        for entry in entries:
            if entry.is_dir(follow_symlinks=False) and entry.name not in SKIP_DIRS and not entry.name.startswith("."):
                walk(entry.path, remaining - 1)

    walk(root, depth)
    return found


def read_package(path):
    try:
        with open(os.path.join(path, "package.json")) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def exists(path, *parts):
    return os.path.exists(os.path.join(path, *parts))


def count(path, *parts):
    target = os.path.join(path, *parts)
    return len(os.listdir(target)) if os.path.isdir(target) else 0


def describe(path):
    info = {"path": path, "name": os.path.basename(path)}
    info["currentBranch"] = git(path, "branch", "--show-current") or "(detached)"
    info["head"] = git(path, "rev-parse", "HEAD")
    info["shallow"] = git(path, "rev-parse", "--is-shallow-repository") == "true"
    roots = git(path, "rev-list", "--max-parents=0", "HEAD")
    info["rootCommits"] = sorted(roots.split()) if roots else []
    info["commitCount"] = int(git(path, "rev-list", "--count", "HEAD") or 0) if info["head"] else 0
    info["branches"] = (git(path, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes") or "").split()
    remotes = {}
    for line in (git(path, "remote", "-v") or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1] == "(fetch)":
            remotes[parts[0]] = redact(parts[1])
    info["remotes"] = remotes
    upstream = git(path, "rev-parse", "--abbrev-ref", "@{upstream}")
    if upstream:
        counts = (git(path, "rev-list", "--left-right", "--count", "%s...HEAD" % upstream) or "").split()
        info["tracking"] = {"remoteRef": upstream, "behind": int(counts[0]), "ahead": int(counts[1])} if len(counts) == 2 else None
    status = (git(path, "status", "--porcelain") or "").splitlines()
    info["uncommitted"] = {"staged": sum(1 for s in status if s[:1] not in (" ", "?")),
                           "unstaged": sum(1 for s in status if s[1:2] not in (" ", "?", "")),
                           "untracked": sum(1 for s in status if s.startswith("??"))}
    operations = []
    for marker in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
        rel = git(path, "rev-parse", "--git-path", marker)
        if rel and os.path.exists(rel if os.path.isabs(rel) else os.path.join(path, rel)):
            operations.append(marker)
    info["unfinishedOperations"] = operations

    package = read_package(path) or {}
    deps = {}
    for section in ("dependencies", "devDependencies"):
        deps.update(package.get(section) or {})
    frameworks = [name for name, key in (
        ("next", "next"), ("react", "react"), ("vue", "vue"), ("nuxt", "nuxt"), ("express", "express"),
        ("nestjs", "@nestjs/core"), ("fastify", "fastify"), ("vite", "vite"),
        ("tanstack-start", "@tanstack/react-start"), ("prisma", "prisma"), ("typeorm", "typeorm"),
        ("drizzle", "drizzle-orm"),
    ) if key in deps]
    info["packageName"] = package.get("name")
    info["frameworks"] = frameworks
    info["packageManager"] = next((pm for pm, lock in (("npm", "package-lock.json"), ("pnpm", "pnpm-lock.yaml"),
                                                       ("yarn", "yarn.lock"), ("bun", "bun.lockb"), ("bun", "bun.lock"))
                                   if exists(path, lock)), None)
    signals = {
        "supabaseClientDependency": "@supabase/supabase-js" in deps,
        "lovableDependencies": sorted(d for d in deps if d.startswith("@lovable.dev/") or d == "lovable-tagger"),
        "supabaseFolder": exists(path, "supabase"),
        "supabaseMigrations": count(path, "supabase", "migrations"),
        "supabaseFunctions": count(path, "supabase", "functions"),
        "supabaseIntegration": exists(path, "src", "integrations", "supabase"),
        "lovableFolder": exists(path, ".lovable"),
        "migrationDocs": exists(path, "docs", "migration"),
        "openapi": exists(path, "openapi"),
        "syncRef": exists(path, ".lovable-sync", "sync-ref.json"),
        "dockerCompose": any(exists(path, f) for f in ("docker-compose.yml", "docker-compose.dev.yml", "compose.yaml")),
    }
    info["signals"] = signals

    hints = []
    lovable = signals["lovableDependencies"] or signals["lovableFolder"] or signals["supabaseIntegration"]
    if lovable and signals["supabaseClientDependency"]:
        hints.append({"role": "source", "evidence": "Lovable tooling and a Supabase client dependency"})
    if {"express", "nestjs", "fastify"} & set(frameworks):
        evidence = "server framework (%s)" % ", ".join(sorted({"express", "nestjs", "fastify"} & set(frameworks)))
        if signals["migrationDocs"]:
            evidence += " and docs/migration from lovable-supabase-migration"
        hints.append({"role": "backend", "evidence": evidence})
    is_source = any(h["role"] == "source" for h in hints)
    if {"next", "react", "vue", "nuxt"} & set(frameworks) and not ({"express", "nestjs"} & set(frameworks)) \
            and not is_source:
        evidence = "UI framework (%s)" % ", ".join(sorted({"next", "react", "vue", "nuxt"} & set(frameworks)))
        if not signals["supabaseClientDependency"]:
            evidence += " without a Supabase client"
        hints.append({"role": "frontend", "evidence": evidence})
    info["roleHints"] = hints
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("workspace")
    parser.add_argument("--depth", type=int, default=2, help="folder levels to search (default 2)")
    args = parser.parse_args()
    root = os.path.abspath(os.path.expanduser(args.workspace))
    if not os.path.isdir(root):
        sys.stderr.write("error: %s is not a directory\n" % root)
        return 1
    repos = [describe(path) for path in find_repos(root, args.depth)]
    root_groups = {}
    for repo in repos:
        for commit in repo["rootCommits"]:
            root_groups.setdefault(commit, []).append(repo["path"])
    state_path = os.path.join(root, ".lovable-sync", "sync-state.json")
    json.dump({
        "workspace": root,
        "existingSyncState": state_path if os.path.exists(state_path) else None,
        "repositories": repos,
        "sharedHistory": [paths for paths in root_groups.values() if len(paths) > 1],
        "note": "role hints are evidence only; confirm every role with the user",
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
