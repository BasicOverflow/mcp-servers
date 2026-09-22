# Notes MCP (showcase)

Slim Obsidian-vault MCP redesigned on **MCP Python SDK v2** (Streamable HTTP), matching the `metrics_mcp` branch style.

> **Not deployed.** Do not run this on insights-host. Notes MCP was removed from the lab; the vault lives on Syncthing/NFS and is used locally. This branch is a reference implementation only.

## Endpoint (local showcase only)

| | |
|---|---|
| Default bind | `127.0.0.1:8000` |
| MCP URL | `http://127.0.0.1:8000/mcp` |
| Health | `http://127.0.0.1:8000/health` |
| Vault | `VAULT_ROOT` or bundled `sample-vault/` |

## Tools (6)

| Tool | Purpose |
|------|---------|
| `vault_info` | Root path + note/dir counts |
| `list_directory` | List files/dirs under a path |
| `read_note` | Read a note (`.md` optional) |
| `write_note` | Write/overwrite (creates parents) |
| `search_filename` | Glob match on filenames |
| `search_content` | Substring search in `*.md` |

Removed vs the old server: delete/move/copy/batch helpers, custom FastAPI/SSE shim, ansible deploy playbook.

## Resources

- `notes://vault` — vault metadata  
- `notes://note/{path}` — note body  

## Prompts

- `locate_and_summarize`  
- `draft_update`  

## Local run

```bash
pip install -r requirements.txt
set PYTHONPATH=src
set VAULT_ROOT=%CD%\sample-vault
python -m notes_mcp
```

Optional Docker (profile-gated so it will not start by accident):

```bash
docker compose --profile showcase up --build
```

## Do not

- Add this to Cursor MCP on machines that should only talk to Metrics MCP  
- Deploy to `10.0.121.218` or restore Notes MCP on `:8083` in the lab  
