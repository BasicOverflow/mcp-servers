# Notes MCP

Markdown vault MCP for LLM agents. Built with **MCP Python SDK v2** (Streamable HTTP).

Point it at any directory of notes with `VAULT_ROOT` (defaults to bundled `sample-vault/`).

## Endpoint

| | |
|---|---|
| MCP | `http://127.0.0.1:8000/mcp` |
| Health | `http://127.0.0.1:8000/health` |
| Vault | env `VAULT_ROOT` or `sample-vault/` |

## Tools

| Tool | Purpose |
|------|---------|
| `vault_info` | Root path + note/dir counts |
| `list_directory` | List files/dirs under a path |
| `read_note` | Read a note (`.md` optional) |
| `write_note` | Write/overwrite (creates parents) |
| `search_filename` | Glob match on filenames |
| `search_content` | Substring search in `*.md` |

## Resources

- `notes://vault` — vault metadata  
- `notes://note/{path}` — note body  

## Prompts

- `locate_and_summarize`  
- `draft_update`  

## Run

```bash
pip install -r requirements.txt
set PYTHONPATH=src
set VAULT_ROOT=%CD%\sample-vault
python -m notes_mcp
```

```bash
docker compose up -d --build
```
