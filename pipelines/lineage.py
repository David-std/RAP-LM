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
    head = (git / "HEAD").read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return head  # detached HEAD
    ref = head[5:]
    loose = git / ref
    if loose.exists():
        return loose.read_text(encoding="utf-8").strip()
    packed = git / "packed-refs"
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
