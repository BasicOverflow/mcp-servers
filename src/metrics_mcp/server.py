"""Metrics MCP server (MCP Python SDK v2 — Streamable HTTP).

Prometheus query + analysis tools for LLM agents.
"""

from __future__ import annotations

import json
import os
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from . import __version__
from . import analysis as A
from .prometheus import prom
from .recipes import RECIPES, suggest_for_task

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
    "metrics-mcp",
    version=__version__,
    instructions=(
        "Prometheus analysis MCP. Prefer infra_overview / list_targets first, "
        "then recipes or PromQL tools. Recipes assume common job labels "
        "(node, proxmox-*, truenas, truenas-zfs) when those exporters exist."
    ),
)


def _j(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def _err(msg: str) -> str:
    return _j({"error": msg})


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> Response:
    """Liveness probe (unauthenticated)."""
    return JSONResponse({"status": "ok", "service": "metrics-mcp", "version": __version__})


# ----- Tools -----


@mcp.tool()
async def prometheus_health() -> str:
    """Check Prometheus readiness and list configured base URL."""
    try:
        return _j(await prom.health())
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def list_targets() -> str:
    """List Prometheus scrape targets with health, job, and last error."""
    try:
        data = await prom.targets()
        rows = []
        for t in data.get("activeTargets", []):
            labels = t.get("labels") or {}
            rows.append(
                {
                    "health": t.get("health"),
                    "job": labels.get("job"),
                    "instance": labels.get("instance"),
                    "host": labels.get("host") or labels.get("node"),
                    "scrapeUrl": t.get("scrapeUrl"),
                    "lastError": t.get("lastError") or None,
                }
            )
        rows.sort(key=lambda r: (r.get("job") or "", r.get("instance") or ""))
        up = sum(1 for r in rows if r["health"] == "up")
        return _j({"up": up, "total": len(rows), "targets": rows})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def list_metrics(prefix: str = "", limit: int = 200) -> str:
    """List metric names, optionally filtered by prefix (e.g. 'node_', 'pve_', 'zfsprom_')."""
    try:
        names = await prom.metric_names()
        if prefix:
            names = [n for n in names if n.startswith(prefix)]
        names = sorted(names)
        return _j({"count": len(names), "returned": min(limit, len(names)), "metrics": names[:limit]})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def metric_info(metric_name: str) -> str:
    """Get Prometheus metadata (type/help) and sample label sets for a metric."""
    try:
        meta = await prom.metadata(metric_name)
        series = await prom.series([metric_name], time_range="1h")
        label_keys: set[str] = set()
        for s in series:
            label_keys.update(k for k in s if k != "__name__")
        return _j(
            {
                "metric": metric_name,
                "metadata": meta,
                "series_count_1h": len(series),
                "label_keys": sorted(label_keys),
                "sample_series": series[:10],
            }
        )
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def label_values(label: str) -> str:
    """List all values for a Prometheus label (e.g. job, host, instance, nodename)."""
    try:
        vals = await prom.label_values(label)
        return _j({"label": label, "count": len(vals), "values": sorted(vals)})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def query_instant(query: str, limit: int = 50) -> str:
    """Run a PromQL instant query. Returns latest samples."""
    try:
        results = await prom.instant(query)
        return _j({"query": query, "series": len(results), "data": A.format_instant(results, limit)})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def query_range(query: str, time_range: str = "1h", step: str = "", limit_series: int = 20) -> str:
    """Run a PromQL range query (e.g. time_range='6h'). Summarizes each series."""
    try:
        results = await prom.range_query(query, time_range, step or None)
        return _j(
            {
                "query": query,
                "time_range": time_range,
                "series": len(results),
                "summaries": A.summarize_series(results, limit_series),
            }
        )
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def series_stats(query: str, time_range: str = "1h") -> str:
    """Compute mean/min/max/std and percentiles (p50/p95/p99) over a range query."""
    try:
        results = await prom.range_query(query, time_range)
        return _j({"query": query, "time_range": time_range, "series": A.summarize_series(results)})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def detect_trend(query: str, time_range: str = "6h") -> str:
    """Linear trend detection (direction, slope, r²) per series."""
    try:
        results = await prom.range_query(query, time_range)
        return _j({"query": query, "time_range": time_range, "trends": A.detect_trend(results)})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def detect_anomalies(query: str, time_range: str = "24h", z_threshold: float = 3.0) -> str:
    """Flag points with |z-score| >= threshold within the range."""
    try:
        results = await prom.range_query(query, time_range)
        return _j(
            {
                "query": query,
                "time_range": time_range,
                "results": A.detect_anomalies(results, z_threshold),
            }
        )
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def correlate_metrics(query_a: str, query_b: str, time_range: str = "6h") -> str:
    """Pearson correlation between the first series of two PromQL range queries."""
    try:
        a = await prom.range_query(query_a, time_range)
        b = await prom.range_query(query_b, time_range)
        return _j(
            {
                "query_a": query_a,
                "query_b": query_b,
                "time_range": time_range,
                "correlation": A.correlate_two(a, b),
            }
        )
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def capacity_forecast(
    query: str,
    threshold: float,
    time_range: str = "7d",
    horizon_hours: float = 168.0,
) -> str:
    """Linear forecast: estimate when each series hits threshold (absolute value)."""
    try:
        results = await prom.range_query(query, time_range)
        return _j(
            {
                "query": query,
                "threshold": threshold,
                "time_range": time_range,
                "horizon_hours": horizon_hours,
                "forecasts": A.capacity_forecast(results, threshold, horizon_hours),
            }
        )
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def suggest_queries(task: str) -> str:
    """Suggest PromQL recipes from a natural-language task."""
    return _j({"task": task, "suggestions": suggest_for_task(task)})


@mcp.tool()
async def list_recipes() -> str:
    """List built-in PromQL recipes (node / PVE / ZFS-oriented)."""
    return _j({"recipes": [{"id": k, **v} for k, v in RECIPES.items()]})


@mcp.tool()
async def run_recipe(recipe_id: str, time_range: str = "1h", mode: str = "instant") -> str:
    """Execute a built-in recipe by id. mode=instant|range|stats|trend|anomalies."""
    if recipe_id not in RECIPES:
        return _err(f"unknown recipe '{recipe_id}'; known={list(RECIPES)}")
    query = RECIPES[recipe_id]["query"]
    try:
        if mode == "instant":
            data = A.format_instant(await prom.instant(query))
            return _j({"recipe_id": recipe_id, "mode": mode, "query": query, "data": data})
        results = await prom.range_query(query, time_range)
        if mode == "range":
            payload: Any = A.summarize_series(results)
        elif mode == "stats":
            payload = A.summarize_series(results)
        elif mode == "trend":
            payload = A.detect_trend(results)
        elif mode == "anomalies":
            payload = A.detect_anomalies(results)
        else:
            return _err("mode must be instant|range|stats|trend|anomalies")
        return _j(
            {
                "recipe_id": recipe_id,
                "mode": mode,
                "query": query,
                "time_range": time_range,
                "results": payload,
            }
        )
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def down_targets() -> str:
    """List scrape targets that are down or reporting lastError."""
    try:
        data = await prom.targets()
        bad = []
        for t in data.get("activeTargets", []):
            labels = t.get("labels") or {}
            health = t.get("health")
            err = t.get("lastError") or ""
            if health != "up" or err:
                bad.append(
                    {
                        "health": health,
                        "job": labels.get("job"),
                        "instance": labels.get("instance"),
                        "host": labels.get("host") or labels.get("node"),
                        "scrapeUrl": t.get("scrapeUrl"),
                        "lastError": err or None,
                        "lastScrape": t.get("lastScrape"),
                    }
                )
        return _j({"down_or_error": len(bad), "targets": bad})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def zfs_pool_summary() -> str:
    """ZFS pool alloc/free/used% from zfsprom_* metrics."""
    try:
        def _pool_key(labels: dict[str, str]) -> tuple[str, ...]:
            return (
                labels.get("pool") or "",
                labels.get("source") or "",
                labels.get("instance") or "",
            )

        alloc_map = {
            _pool_key(r.get("metric") or {}): r.get("value")
            for r in A.format_instant(await prom.instant('zfsprom_alloc{type="pool"}'))
        }
        free_rows = A.format_instant(await prom.instant('zfsprom_free{type="pool"}'))
        rows = []
        for fr in free_rows:
            labels = fr.get("metric") or {}
            key = _pool_key(labels)
            alloc_b = alloc_map.get(key)
            free_b = fr.get("value")
            total = None
            used_pct = None
            if alloc_b is not None and free_b is not None:
                total = alloc_b + free_b
                if total > 0:
                    used_pct = 100.0 * alloc_b / total
            rows.append(
                {
                    "pool": labels.get("pool") or labels.get("source"),
                    "labels": {k: v for k, v in labels.items() if k != "__name__"},
                    "alloc_bytes": alloc_b,
                    "free_bytes": free_b,
                    "total_bytes": total,
                    "used_pct": used_pct,
                }
            )
        rows.sort(key=lambda r: r.get("used_pct") or 0, reverse=True)
        return _j({"pools": rows})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def infra_overview() -> str:
    """Health snapshot: targets, node CPU/mem, guest counts, ZFS pools."""
    try:
        targets = await prom.targets()
        active = targets.get("activeTargets", [])
        tgt = [
            {
                "health": t.get("health"),
                "job": (t.get("labels") or {}).get("job"),
                "instance": (t.get("labels") or {}).get("instance"),
                "host": (t.get("labels") or {}).get("host") or (t.get("labels") or {}).get("node"),
                "error": t.get("lastError") or None,
            }
            for t in active
        ]
        up = sum(1 for t in tgt if t["health"] == "up")

        node_cpu = A.format_instant(
            await prom.instant(
                '100 * (1 - avg by (host) (rate(node_cpu_seconds_total{job="node",mode="idle"}[5m])))'
            )
        )
        node_mem = A.format_instant(
            await prom.instant(
                '100 * (1 - node_memory_MemAvailable_bytes{job="node"} / node_memory_MemTotal_bytes{job="node"})'
            )
        )
        guests = A.format_instant(await prom.instant("count by (type) (pve_guest_info)"))
        zfs = A.format_instant(await prom.instant('zfsprom_alloc{type="pool"}'))
        zfs_free = A.format_instant(await prom.instant('zfsprom_free{type="pool"}'))

        return _j(
            {
                "prometheus": await prom.health(),
                "targets": {"up": up, "total": len(tgt), "items": tgt},
                "node_cpu_busy_pct": node_cpu,
                "node_memory_used_pct": node_mem,
                "pve_guest_counts": guests,
                "zfs_alloc_bytes": zfs,
                "zfs_free_bytes": zfs_free,
            }
        )
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def compare_hosts(metric: str = "cpu", time_range: str = "1h") -> str:
    """Compare hosts for cpu|memory|load|disk over a time range (job=node)."""
    queries = {
        "cpu": '100 * (1 - avg by (host) (rate(node_cpu_seconds_total{job="node",mode="idle"}[5m])))',
        "memory": '100 * (1 - avg by (host) (node_memory_MemAvailable_bytes{job="node"} / node_memory_MemTotal_bytes{job="node"}))',
        "load": 'avg by (host) (node_load1{job="node"})',
        "disk": '100 * (1 - avg by (host) (node_filesystem_avail_bytes{job="node",mountpoint="/",fstype!="rootfs"} / node_filesystem_size_bytes{job="node",mountpoint="/",fstype!="rootfs"}))',
    }
    if metric not in queries:
        return _err(f"metric must be one of {list(queries)}")
    try:
        results = await prom.range_query(queries[metric], time_range)
        up_hosts: set[str] = set()
        for t in (await prom.targets()).get("activeTargets", []):
            labels = t.get("labels") or {}
            if labels.get("job") == "node" and t.get("health") == "up" and labels.get("host"):
                up_hosts.add(labels["host"])
        summaries = A.summarize_series(results, max_series=50)
        if up_hosts:
            filtered = [s for s in summaries if (s.get("labels") or {}).get("host") in up_hosts]
            if filtered:
                summaries = filtered
        return _j(
            {
                "metric": metric,
                "query": queries[metric],
                "time_range": time_range,
                "active_hosts": sorted(up_hosts),
                "hosts": summaries,
            }
        )
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def top_guests(resource: str = "cpu", limit: int = 10) -> str:
    """Top QEMU/LXC guests by cpu or memory from PVE exporter metrics."""
    if resource == "cpu":
        q = "topk(50, pve_cpu_usage_ratio{id=~\"qemu/.+|lxc/.+\"})"
    elif resource == "memory":
        q = "topk(50, pve_memory_usage_bytes{id=~\"qemu/.+|lxc/.+\"})"
    else:
        return _err("resource must be cpu or memory")
    try:
        data = A.format_instant(await prom.instant(q), limit=100)
        best: dict[str, dict[str, Any]] = {}
        for row in data:
            gid = (row.get("metric") or {}).get("id") or ""
            name = (row.get("metric") or {}).get("name")
            val = row.get("value")
            if not gid or val is None:
                continue
            prev = best.get(gid)
            if prev is None or (val or 0) > (prev.get("value") or 0):
                best[gid] = {
                    "id": gid,
                    "name": name,
                    "node": (row.get("metric") or {}).get("node"),
                    "value": val,
                    "metric": row.get("metric"),
                }
        top = sorted(best.values(), key=lambda x: x.get("value") or 0, reverse=True)[:limit]
        return _j({"resource": resource, "query": q, "top": top})
    except Exception as e:
        return _err(str(e))


# ----- Resources -----


@mcp.resource("metrics://recipes")
def recipes_index() -> str:
    """Index of built-in PromQL recipes."""
    return _j([{"id": k, **v} for k, v in RECIPES.items()])


@mcp.resource("metrics://recipes/{recipe_id}")
def recipe_detail(recipe_id: str) -> str:
    """A single PromQL recipe by id."""
    if recipe_id not in RECIPES:
        return _j({"error": f"unknown recipe '{recipe_id}'", "known": list(RECIPES)})
    return _j({"id": recipe_id, **RECIPES[recipe_id]})


@mcp.resource("metrics://stack")
def stack_description() -> str:
    """Describe expected scrape jobs for the built-in recipes."""
    return _j(
        {
            "prometheus": os.getenv("PROMETHEUS_URL", "http://127.0.0.1:9090"),
            "assumed_jobs": {
                "node": "node_exporter (host OS metrics)",
                "proxmox-*": "prometheus-pve-exporter (guest/node via PVE API)",
                "truenas": "Graphite-style TrueNAS metrics (scale_monitoring_*)",
                "truenas-zfs": "zfsprom_* pool metrics",
            },
            "note": "Recipes are optional conveniences; any PromQL works via query_* tools.",
        }
    )


# ----- Prompts -----


@mcp.prompt()
def investigate_incident(symptom: str = "high latency or resource pressure") -> str:
    """Guided prompt for investigating a metrics incident."""
    return (
        f"Investigate this symptom using the metrics-mcp tools: {symptom}\n"
        "1) Call infra_overview and list_targets.\n"
        "2) Use suggest_queries for the symptom, then series_stats / detect_anomalies on the best queries.\n"
        "3) If a host looks bad, compare_hosts and top_guests.\n"
        "4) If storage related, check zfs_* recipes and SMART temp recipes.\n"
        "5) Summarize root cause hypotheses with supporting numbers."
    )


@mcp.prompt()
def capacity_review(horizon: str = "7d") -> str:
    """Prompt for a capacity planning pass over hosts and ZFS pools."""
    return (
        f"Perform a capacity review for the next {horizon}.\n"
        "Use compare_hosts for cpu/memory/disk, capacity_forecast on filesystem and zfsprom_alloc series "
        "with sensible thresholds, and top_guests for CPU/memory hot spots. "
        "End with prioritized recommendations."
    )


@mcp.prompt()
def explain_metric(metric_name: str) -> str:
    """Prompt to explain a Prometheus metric."""
    return (
        f"Explain metric '{metric_name}'. "
        "Use metric_info, then query_instant with a small example. "
        "Note which job/exporter produces it and how an agent should interpret spikes."
    )


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_ALLOWED_HOSTS,
        allowed_origins=_ALLOWED_ORIGINS,
    )
    # Stateless Streamable HTTP — MCP 2025/2026 deployable transport
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