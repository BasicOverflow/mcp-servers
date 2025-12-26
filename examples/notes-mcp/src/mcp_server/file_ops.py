"""File operations and path resolution utilities."""

import os
from pathlib import Path


def get_vault_root() -> Path:
    """Get the vault root path from environment variable."""
    vault_path = os.getenv("VAULT_PATH", "/app/vault")
    return Path(vault_path).resolve()


def normalize_path(path: str) -> str:
    """Normalize path - add .md extension if missing."""
    path = path.strip()
    if not path.endswith(".md") and "." not in os.path.basename(path):
        path = f"{path}.md"
    return path


def validate_path(path: Path, vault_root: Path) -> bool:
    """Validate that path is within vault root."""
    try:
        resolved = path.resolve()
        return str(resolved).startswith(str(vault_root.resolve()))
    except (ValueError, OSError):
        return False


def resolve_path(path: str, normalize: bool = True) -> Path:
    """Resolve and validate a path relative to vault root."""
    vault_root = get_vault_root()
    path_str = path.strip()
    
    if not path_str:
        raise ValueError("Path cannot be empty")
    
    if normalize:
        normalized = normalize_path(path_str)
    else:
        normalized = path_str
    
    if os.path.isabs(normalized):
        resolved = Path(normalized)
    else:
        resolved = vault_root / normalized
    
    if not validate_path(resolved, vault_root):
        raise ValueError(f"Path traversal detected: {path}")
    
    return resolved.resolve()

