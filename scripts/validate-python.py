#!/usr/bin/env python3
# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.

"""Python code validation gate for cyql.

Runs the project's static and security checks in one place, so the same gate is
used locally before committing and in CI:

- syntax (AST compilation) over the package, tools, tests, and this script
- ruff lint (the repo's documented lint gate — ``ruff check``)
- mypy (strict, per ``pyproject.toml``)
- bandit (security scan over the shipped package)
- pip-audit (known-vulnerability scan over the declared runtime dependencies)

Usage:
    uv run python scripts/validate-python.py [--fix]

Options:
    --fix    Auto-fix lint issues with ``ruff check --fix``.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

_APP_DIR = "src/cyql"
_SYNTAX_DIRS = ["src", "tools", "tests", "scripts"]
_EXCLUDE_DIRS = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    "build",
    "dist",
}
_MAX_ISSUES = 10


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, capturing its output."""
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _find_py_files(dirs: list[str]) -> list[str]:
    """Return every ``.py`` file under ``dirs``, skipping excluded directories."""
    files: list[str] = []
    for base in dirs:
        for root, dnames, fnames in os.walk(base):
            dnames[:] = [d for d in dnames if d not in _EXCLUDE_DIRS]
            files.extend(str(Path(root) / f) for f in fnames if f.endswith(".py"))
    return sorted(files)


def check_syntax() -> bool:
    """AST-compile every Python file in the scanned directories."""
    print("\n== Syntax (AST) ==")
    ok = True
    files = _find_py_files(_SYNTAX_DIRS)
    for path in files:
        try:
            ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
        except SyntaxError as exc:
            print(f"  FAIL: {path}:{exc.lineno}:{exc.offset}: {exc.msg}")
            ok = False
    if ok:
        print(f"  ok: {len(files)} files")
    return ok


def check_ruff(*, fix: bool) -> bool:
    """Lint with ruff (the repo's documented gate)."""
    print("\n== Ruff (lint) ==")
    cmd = ["python", "-m", "ruff", "check"]
    if fix:
        cmd.append("--fix")
    cmd.append(".")
    result = _run(cmd)
    if result.returncode == 0:
        print("  ok: no lint issues")
        return True
    print(result.stdout or result.stderr)
    print("  FAIL: ruff check")
    return False


def check_mypy() -> bool:
    """Type-check with mypy (strict, configured in pyproject.toml)."""
    print("\n== mypy ==")
    result = _run(["python", "-m", "mypy"])
    if result.returncode == 0:
        print("  ok: type checking passed")
        return True
    print(result.stdout or result.stderr)
    print("  FAIL: mypy")
    return False


def check_bandit() -> bool:
    """Security-scan the shipped package with bandit."""
    print("\n== Bandit (security) ==")
    result = _run(
        ["python", "-m", "bandit", "-r", _APP_DIR, "-f", "json", "-l", "-i", "--quiet"]
    )
    try:
        issues = json.loads(result.stdout).get("results", [])
    except (json.JSONDecodeError, ValueError):
        print(result.stdout or result.stderr)
        print("  FAIL: bandit output could not be parsed")
        return False
    if not issues:
        print("  ok: no security issues")
        return True
    for issue in issues[:_MAX_ISSUES]:
        print(
            f"  [{issue.get('issue_severity')}/{issue.get('issue_confidence')}] "
            f"{issue.get('filename')}:{issue.get('line_number')} - "
            f"{issue.get('test_id')}: {issue.get('issue_text')}"
        )
    if len(issues) > _MAX_ISSUES:
        print(f"  ... and {len(issues) - _MAX_ISSUES} more")
    print(f"  FAIL: {len(issues)} security issue(s)")
    return False


def _production_requirements() -> list[str]:
    """Return the runtime dependency specifiers from ``project.dependencies``."""
    with Path("pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    return list(data.get("project", {}).get("dependencies", []))


def check_pip_audit() -> bool:
    """Scan the declared runtime dependencies for known vulnerabilities."""
    print("\n== pip-audit (dependencies) ==")
    specs = _production_requirements()
    if not specs:
        print("  ok: no runtime dependencies declared")
        return True
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write("\n".join(specs) + "\n")
        req_path = tmp.name
    try:
        result = _run(
            ["python", "-m", "pip_audit", "-r", req_path, "--format", "json", "--strict"]
        )
    finally:
        Path(req_path).unlink(missing_ok=True)

    if result.returncode == 0:
        print("  ok: no known vulnerabilities")
        return True
    try:
        dependencies = json.loads(result.stdout).get("dependencies", [])
    except (json.JSONDecodeError, ValueError):
        dependencies = []
    if not dependencies:
        print(result.stdout or result.stderr)
        print("  FAIL: pip-audit failed")
        return False
    for dep in dependencies[:_MAX_ISSUES]:
        for vuln in dep.get("vulns", []):
            print(f"  {dep.get('name')}=={dep.get('version')}: {vuln.get('id')}")
    print("  FAIL: vulnerabilities found")
    return False


def main() -> None:
    """Run the full validation gate."""
    fix = "--fix" in sys.argv
    os.chdir(Path(__file__).resolve().parent.parent)

    checks = [
        ("Syntax", check_syntax()),
        ("Ruff", check_ruff(fix=fix)),
        ("mypy", check_mypy()),
        ("Bandit", check_bandit()),
        ("pip-audit", check_pip_audit()),
    ]

    print("\n== Summary ==")
    for name, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}: {name}")
    if all(ok for _, ok in checks):
        print("All validation checks passed.")
        sys.exit(0)
    print("Some validation checks failed.")
    if not fix:
        print(
            "Run with --fix to auto-fix lint issues: "
            "uv run python scripts/validate-python.py --fix"
        )
    sys.exit(1)


if __name__ == "__main__":
    main()
