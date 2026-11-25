"""Code lineage helpers shared by the batch pipeline (RNF-02, RD-06).

The commit is read from the ``.git`` directory directly so that it does not
depend on a ``git`` executable being on PATH (on Windows, Git is often only
available inside Git Bash). A dirty working tree is flagged, never hidden.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git_sha(root: Path = ROOT) -> str:
    """Return the checked-out commit SHA, or raise if it cannot be determined."""
    git = root / ".git"
    common = git
    if git.is_file():
        # Linked worktree: .git holds "gitdir: <repo>/.git/worktrees/<name>"; branch refs
        # and packed-refs live in the common directory named by its "commondir" file.
        git = (root / git.read_text(encoding="utf-8").split(":", 1)[1].strip()).resolve()
        commondir = git / "commondir"
        if commondir.exists():
            common = (git / commondir.read_text(encoding="utf-8").strip()).resolve()
        else:
            common = git
    head = (git / "HEAD").read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return head  # detached HEAD
    ref = head[5:]
    for base in (git, common):
        loose = base / ref
        if loose.exists():
            return loose.read_text(encoding="utf-8").strip()
    packed = common / "packed-refs"
    if packed.exists():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line.endswith(" " + ref):
                return line.split(" ", 1)[0]
    raise RuntimeError(f"Cannot resolve {ref}: record the code version before running the batch")


def tree_is_clean(root: Path = ROOT, paths: tuple[str, ...] = ("ml", "pipelines")) -> bool | None:
    """True/False when git is available; None when it cannot be checked."""
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain", "--", *paths], cwd=root, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.strip() == ""
