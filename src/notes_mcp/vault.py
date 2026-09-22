"""Safe path helpers for a vault rooted at VAULT_ROOT."""

from __future__ import annotations

import os
from pathlib import Path


def vault_root() -> Path:
    raw = os.getenv("VAULT_ROOT", "").strip()
    if raw:
        root = Path(raw).expanduser().resolve()
        if not root.is_dir():
            raise RuntimeError(f"VAULT_ROOT is not a directory: {root}")
        return root
    here = Path(__file__).resolve().parents[2]
    candidate = here / "sample-vault"
    if candidate.is_dir():
        return candidate.resolve()
    raise RuntimeError("Set VAULT_ROOT or provide sample-vault/ in the repo root")


def _within_vault(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as e:
        raise PermissionError(f"path escapes vault root: {path}") from e
    return resolved


def resolve_dir(path: str = "") -> Path:
    root = vault_root()
    rel = (path or "").strip().replace("\\", "/").lstrip("/")
    target = root if not rel else root / rel
    resolved = _within_vault(target, root)
    if not resolved.exists():
        raise FileNotFoundError(f"directory not found: {path or '/'}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"not a directory: {path}")
    return resolved


def resolve_file(path: str, *, for_write: bool = False) -> Path:
    """Resolve a note path; auto-append .md when no suffix is given."""
    root = vault_root()
    rel = (path or "").strip().replace("\\", "/").lstrip("/")
    if not rel:
        raise ValueError("path is required")

    raw = root / rel
    if Path(rel).suffix:
        candidates = [raw]
    else:
        candidates = [root / f"{rel}.md", raw]

    if for_write:
        chosen = candidates[0]
        parent = chosen.parent
        _within_vault(parent if parent != chosen else root, root)
        return _within_vault(chosen, root)

    for c in candidates:
        resolved = _within_vault(c, root)
        if resolved.exists() and resolved.is_file():
            return resolved
    raise FileNotFoundError(f"not found: {path}")


def rel_to_vault(path: Path) -> str:
    return path.resolve().relative_to(vault_root()).as_posix()
