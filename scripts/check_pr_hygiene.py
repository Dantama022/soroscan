#!/usr/bin/env python3
"""Fail a pull request that adds build artifacts, secrets, or unsafe CI changes.

This is a deliberately small, dependency-free gate. It complements gitleaks
(which scans for secret *values*) by rejecting the *kinds of files* and
*workflow constructs* that malicious or careless contributions use to smuggle
code past review:

* compiled Python bytecode / caches (``__pycache__/``, ``*.pyc``)
* vendored ``node_modules/`` and local agent workspaces
* private keys, keystores, and real ``.env`` files
* binaries (``git diff --numstat`` reports ``-``)
* ``pull_request_target`` and ``permissions: write-all`` in workflows
* a PR that deletes every (or most) CI workflow

Usage::

    python3 scripts/check_pr_hygiene.py --base origin/dev --head HEAD
    python3 scripts/check_pr_hygiene.py --base "$BASE_SHA" --head "$HEAD_SHA"

A maintainer can bypass the gate by adding the ``hygiene-override`` label
(only users with write access can label a PR).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

DISALLOWED_PATHS = [
    (re.compile(r"(^|/)__pycache__/"), "Python bytecode cache directory"),
    (re.compile(r"\.py[cod]$"), "compiled Python file"),
    (re.compile(r"(^|/)\.pytest_cache/"), "pytest cache"),
    (re.compile(r"(^|/)node_modules/"), "vendored Node modules"),
    (re.compile(r"(^|/)\.agent(s)?/"), "local agent workspace"),
    (re.compile(r"(^|/)CLI_REMEDIATION_PROMPT.*\.md$"), "agent remediation prompt"),
    (re.compile(r"(^|/)\.DS_Store$"), "macOS metadata"),
    (re.compile(r"\.(pem|key|p12|pfx|jks|keystore)$"), "private key or keystore"),
    (re.compile(r"(^|/)\.env$"), "environment file (commit .env.example instead)"),
]

DANGEROUS_WORKFLOW_LINES = [
    (re.compile(r"\bpull_request_target\b"), "pull_request_target runs with repository secrets"),
    (re.compile(r"permissions:\s*write-all"), "write-all token permissions are too broad"),
]

MAX_FILE_BYTES = 1_000_000
WORKFLOW_PREFIX = ".github/workflows/"
# Lockfiles legitimately exceed the generic size limit.
LOCKFILE_NAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.lock",
    "poetry.lock",
    "Pipfile.lock",
}


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    )
    return result.stdout


def changed_entries(base: str, head: str) -> list[tuple[str, str]]:
    """Return ``(status, path)`` for added/modified/renamed files."""
    out = git("diff", "--name-status", "--find-renames", base, head)
    entries = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            entries.append((parts[0][0], parts[-1]))
    return entries


def numstat(base: str, head: str) -> dict[str, tuple[str, str]]:
    out = git("diff", "--numstat", base, head)
    stats: dict[str, tuple[str, str]] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            stats[parts[-1]] = (parts[0], parts[1])
    return stats


def added_lines(path: str, base: str, head: str) -> list[tuple[int, str]]:
    """Return ``(line_number, text)`` for added lines in *path*."""
    out = git("diff", "-U0", base, head, "--", path)
    lines: list[tuple[int, str]] = []
    new_line = 0
    for raw in out.splitlines():
        if raw.startswith("@@"):
            match = re.search(r"\+(\d+)", raw)
            new_line = int(match.group(1)) if match else 0
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            lines.append((new_line, raw[1:]))
            new_line += 1
        elif raw.startswith(" "):
            new_line += 1
    return lines


def workflows_at(rev: str) -> set[str]:
    out = git("ls-tree", "-r", "--name-only", rev, "--", WORKFLOW_PREFIX)
    return {
        line
        for line in out.splitlines()
        if line.endswith((".yml", ".yaml"))
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="base commit/ref")
    parser.add_argument("--head", required=True, help="head commit/ref")
    parser.add_argument(
        "--labels",
        default=os.environ.get("PR_LABELS", ""),
        help="comma-separated PR labels (maintainer override)",
    )
    args = parser.parse_args()

    override = "hygiene-override" in {
        label.strip() for label in args.labels.split(",") if label.strip()
    }

    errors: list[str] = []
    warnings: list[str] = []

    stats = numstat(args.base, args.head)

    for status, path in changed_entries(args.base, args.head):
        for pattern, reason in DISALLOWED_PATHS:
            if pattern.search(path):
                errors.append(f"{path}: {reason} must not be committed")
                break

        if status == "D":
            continue

        added, _deleted = stats.get(path, ("0", "0"))
        if added == "-":
            errors.append(f"{path}: binary files are not allowed in a PR")

        # Size check (skip paths that do not exist at head, e.g. renamed away).
        try:
            size = int(git("cat-file", "-s", f"{args.head}:{path}").strip())
        except subprocess.CalledProcessError:
            size = 0
        if size > MAX_FILE_BYTES and path.rsplit("/", 1)[-1] not in LOCKFILE_NAMES:
            errors.append(
                f"{path}: {size} bytes exceeds the {MAX_FILE_BYTES} byte limit"
            )

        if path.startswith(WORKFLOW_PREFIX):
            for line_number, text in added_lines(path, args.base, args.head):
                for pattern, reason in DANGEROUS_WORKFLOW_LINES:
                    if pattern.search(text):
                        errors.append(f"{path}:{line_number}: {reason}")

    # Refuse a PR that wipes out the CI suite (the pattern used by PR #1859).
    base_workflows = workflows_at(args.base)
    deleted_workflows = {
        path
        for path in base_workflows
        if git("diff", "--name-status", "--diff-filter=D", args.base, args.head, "--", path)
        .strip()
        .startswith("D")
    }
    if base_workflows and deleted_workflows == base_workflows:
        errors.append("PR deletes every CI workflow")
    elif len(deleted_workflows) >= 5:
        errors.append(
            f"PR deletes {len(deleted_workflows)} CI workflows; "
            "split this up or get explicit maintainer sign-off"
        )

    if override:
        if errors:
            print("::warning::hygiene-override label present; violations are warnings only")
            warnings.extend(errors)
            errors = []

    for message in errors:
        print(f"::error::{message}")
    for message in warnings:
        print(f"::warning::{message}")

    if errors:
        print(f"\n{len(errors)} hygiene violation(s) found.", file=sys.stderr)
        return 1

    print("PR hygiene checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
