# Metrics MCP

LLM-facing Model Context Protocol server for the homelab Prometheus stack on **insights-host**.

Implements **MCP Python SDK v2** (`mcp>=2.0`) with **Streamable HTTP** (stateless + JSON responses) per the current MCP transport model.

## Endpoint

| | |
|---|---|
| Host | insights-host `10.0.121.218` |
| URL | `http://10.0.121.218:8084/mcp` |
| Prometheus | `http://10.0.121.218:9090` (env `PROMETHEUS_URL`) |

## Tools

| Tool | Purpose |
|------|---------|
| `prometheus_health` | Ready/healthy check |
| `list_targets` | Scrape target health |
| `list_metrics` | Metric name catalog (prefix filter) |
| `metric_info` | Metadata + sample series |
| `label_values` | Values for a label |
| `query_instant` / `query_range` | Raw PromQL |
| `series_stats` | mean/min/max/p50/p95/p99 |
| `detect_trend` | Linear trend / slope |
| `detect_anomalies` | Z-score outliers |
| `correlate_metrics` | Pearson correlation |
| `capacity_forecast` | ETA to absolute threshold |
| `suggest_queries` / `list_recipes` / `run_recipe` | Homelab-aware PromQL recipes |
| `down_targets` | Targets that are down or errored |
| `zfs_pool_summary` | Pool alloc/free/used% |
| `infra_overview` | One-shot health snapshot |
| `compare_hosts` | CPU/mem/load/disk across Proxmox nodes |
| `top_guests` | Hottest QEMU/LXC by CPU or memory |

## Resources

- `metrics://stack` — scrape topology notes
- `metrics://recipes` — recipe index
- `metrics://recipes/{id}` — single recipe

## Prompts

- `investigate_incident`
- `capacity_review`
- `explain_metric`

## Local run

```bash
pip install -r requirements.txt
set PYTHONPATH=src
set PROMETHEUS_URL=http://10.0.121.218:9090
python -m metrics_mcp
```

## Docker (insights-host)

```bash
docker compose up -d --build
```

Maps host **8084** → container **8000**.

## Cursor / client config (example)

```json
{
  "mcpServers": {
    "metrics": {
      "url": "http://10.0.121.218:8084/mcp"
    }
  }
}
```

(Exact client key names vary by host; use Streamable HTTP / remote MCP URL support.)
