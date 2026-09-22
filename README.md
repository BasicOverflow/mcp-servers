# Metrics MCP

Prometheus analysis MCP for LLM agents. Built with **MCP Python SDK v2** (Streamable HTTP).

Point it at any Prometheus with `PROMETHEUS_URL`. Includes query helpers, stats/trends/anomalies, capacity forecasts, and optional PromQL recipes for common node / PVE / ZFS exporters.

## Endpoint

| | |
|---|---|
| MCP | `http://127.0.0.1:8000/mcp` (default) |
| Health | `http://127.0.0.1:8000/health` |
| Prometheus | env `PROMETHEUS_URL` (default `http://127.0.0.1:9090`) |

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
| `suggest_queries` / `list_recipes` / `run_recipe` | Built-in PromQL recipes |
| `down_targets` | Targets that are down or errored |
| `zfs_pool_summary` | Pool alloc/free/used% |
| `infra_overview` | One-shot health snapshot |
| `compare_hosts` | CPU/mem/load/disk across nodes |
| `top_guests` | Hottest QEMU/LXC by CPU or memory |

## Resources

- `metrics://stack` — expected scrape job notes
- `metrics://recipes` — recipe index
- `metrics://recipes/{id}` — single recipe

## Prompts

- `investigate_incident`
- `capacity_review`
- `explain_metric`

## Run

```bash
pip install -r requirements.txt
set PYTHONPATH=src
set PROMETHEUS_URL=http://127.0.0.1:9090
python -m metrics_mcp
```

```bash
docker compose up -d --build
```

Default compose maps host **8084** → container **8000**.

## Client config

```json
{
  "mcpServers": {
    "metrics": {
      "url": "http://127.0.0.1:8084/mcp"
    }
  }
}
```
