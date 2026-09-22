"""Notes MCP server (MCP Python SDK v2 — Streamable HTTP).

SHOWCASE ONLY — not deployed. Slim Obsidian-vault file tools for reference.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from . import __version__
from . import vault as V

_ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv(
        "MCP_ALLOWED_HOSTS",
        "127.0.0.1,127.0.0.1:*,localhost,localhost:*",
    ).split(",")
    if h.strip()
]
_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "MCP_ALLOWED_ORIGINS",
        "http://127.0.0.1:*,http://localhost:*",
    ).split(",")
    if o.strip()
]

mcp = MCPServer(
    "notes-mcp",
    version=__version__,
    instructions=(
        "SHOWCASE Notes MCP — Obsidian vault file access. "
        "Not deployed in the homelab; prefer local vault / Syncthing. "
        "Use list_directory / search_* before write_note."
    ),
)


def _j(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def _err(msg: str) -> str:
    return _j({"error": msg})


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> Response:
    return JSONResponse({"status": "ok", "service": "notes-mcp", "version": __version__, "showcase": True})


# ----- Tools -----


@mcp.tool()
async def vault_info() -> str:
    """Vault root path plus counts of markdown notes and directories."""
    try:
        root = V.vault_root()
        md = list(root.rglob("*.md"))
        dirs = [p for p in root.rglob("*") if p.is_dir()]
        return _j(
            {
                "root": str(root),
                "markdown_files": len(md),
                "directories": len(dirs),
                "showcase": True,
                "note": "This server is a redesign showcase and is not deployed.",
            }
        )
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def list_directory(path: str = "", limit: int = 200) -> str:
    """List files and subdirectories under a vault-relative path (default: root)."""
    try:
        d = V.resolve_dir(path)
        rows = []
        for child in sorted(d.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name.startswith("."):
                continue
            rows.append(
                {
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "path": V.rel_to_vault(child),
                    "size": child.stat().st_size if child.is_file() else None,
                }
            )
            if len(rows) >= limit:
                break
        return _j({"path": V.rel_to_vault(d) if d != V.vault_root() else "", "count": len(rows), "entries": rows})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def read_note(path: str) -> str:
    """Read a note. Path is vault-relative; .md is optional."""
    try:
        f = V.resolve_file(path)
        text = f.read_text(encoding="utf-8")
        return _j({"path": V.rel_to_vault(f), "bytes": len(text.encode("utf-8")), "content": text})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def write_note(path: str, content: str) -> str:
    """Write/overwrite a note. Creates parent directories. .md appended if no suffix."""
    try:
        f = V.resolve_file(path, for_write=True)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
        return _j({"path": V.rel_to_vault(f), "bytes": f.stat().st_size, "written": True})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def search_filename(pattern: str, limit: int = 50) -> str:
    """Find notes whose filename matches a glob (e.g. '*Insights*', '**/TODO*.md')."""
    try:
        root = V.vault_root()
        matches = []
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            rel = V.rel_to_vault(p)
            if p.match(pattern) or Path(rel).match(pattern) or Path(p.name).match(pattern):
                matches.append({"path": rel, "name": p.name})
            if len(matches) >= limit:
                break
        return _j({"pattern": pattern, "count": len(matches), "matches": matches})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def search_content(query: str, limit: int = 30, context_lines: int = 1) -> str:
    """Case-insensitive substring search across markdown files."""
    try:
        root = V.vault_root()
        q = query.lower()
        hits = []
        for p in root.rglob("*.md"):
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(lines):
                if q not in line.lower():
                    continue
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                hits.append(
                    {
                        "path": V.rel_to_vault(p),
                        "line": i + 1,
                        "snippet": "\n".join(lines[start:end]),
                    }
                )
                if len(hits) >= limit:
                    return _j({"query": query, "count": len(hits), "hits": hits, "truncated": True})
        return _j({"query": query, "count": len(hits), "hits": hits, "truncated": False})
    except Exception as e:
        return _err(str(e))


# ----- Resources -----


@mcp.resource("notes://vault")
def vault_resource() -> str:
    """Describe the configured vault root."""
    try:
        root = V.vault_root()
        return _j(
            {
                "root": str(root),
                "showcase": True,
                "deployed": False,
                "markdown_files": sum(1 for _ in root.rglob("*.md")),
            }
        )
    except Exception as e:
        return _err(str(e))


@mcp.resource("notes://note/{path}")
def note_resource(path: str) -> str:
    """Read a note as a resource (vault-relative path; use -- or / separators)."""
    try:
        # URI templates often encode nested paths with extra segments; accept slashes
        cleaned = path.replace("--", "/")
        f = V.resolve_file(cleaned)
        return f.read_text(encoding="utf-8")
    except Exception as e:
        return _err(str(e))


# ----- Prompts -----


@mcp.prompt()
def locate_and_summarize(topic: str = "insights-host monitoring") -> str:
    """Find notes about a topic and summarize them."""
    return (
        f"Locate vault notes about: {topic}\n"
        "1) search_filename and search_content for the topic.\n"
        "2) read_note on the best 2–3 hits.\n"
        "3) Summarize facts; cite vault-relative paths."
    )


@mcp.prompt()
def draft_update(path: str, change: str = "bring the doc up to date") -> str:
    """Read a note, propose an edit, optionally write it back."""
    return (
        f"Update note '{path}' to: {change}\n"
        "1) read_note.\n"
        "2) Propose a concise patch.\n"
        "3) Only call write_note if the user confirms."
    )


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_ALLOWED_HOSTS,
        allowed_origins=_ALLOWED_ORIGINS,
    )
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
        transport_security=security,
    )


if __name__ == "__main__":
    main()
