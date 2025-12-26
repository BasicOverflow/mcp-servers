# Metrics MCP Server

MCP server that exposes Prometheus metrics analysis capabilities to AI agents. Provides time series operations, multi-series analysis, and infrastructure insights via HTTP/SSE for remote access.

## Overview

The Metrics MCP Server enables AI agents to:
- Discover and explore available Prometheus metrics
- Query metrics with time ranges and label filters
- Perform statistical analysis (percentiles, trends, anomalies)
- Analyze resource utilization across infrastructure
- Get infrastructure health summaries

## Architecture

```
examples/metrics-mcp/
├── src/
│   └── mcp_server/
│       ├── __init__.py
│       ├── server.py              # MCP server with 28+ tools
│       ├── http_server.py          # HTTP/SSE server
│       ├── prometheus_client.py    # Prometheus API client
│       ├── metrics_analysis.py     # Analysis functions (pandas/numpy/scipy)
│       └── metric_discovery.py     # Smart metric discovery & grouping
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Features

### Metric Discovery (3 tools)
- `discover_metrics` - Discover all metrics grouped by exporter/category/resource
- `get_metric_info` - Get detailed info about a specific metric
- `recommend_metrics` - Get recommended metrics for a task (smart filtering)

### Time Series Operations (11 tools)
- `query_metrics` - Query Prometheus for specific metrics
- `calculate_percentiles` - p50, p95, p99
- `calculate_statistics` - mean, median, min, max, std dev
- `calculate_rate` - Rate of change (requests/sec, bytes/sec)
- `calculate_derivative` - Rate of change over time
- `detect_trends` - Upward/downward trends
- `calculate_moving_average` - Smooth out noise (7-day, 30-day)
- `forecast_capacity` - Project future usage
- `detect_anomalies` - Statistical outliers
- `compare_periods` - Week-over-week, month-over-month
- `calculate_growth_rate` - Percentage change
- `find_peak_usage` - Identify peak times/days

### Multi-Series Operations (6 tools)
- `correlate_metrics` - Find relationships (CPU vs memory)
- `compare_series` - Side-by-side comparison
- `calculate_ratios` - Efficiency metrics
- `analyze_resource_utilization` - CPU/RAM/disk across hosts
- `identify_bottlenecks` - Find constrained resources
- `project_capacity_needs` - Forecast resource exhaustion
- `analyze_resource_distribution` - Balance across cluster

### Infrastructure Insights (8 tools)
- `get_resource_usage` - CPU/RAM/disk for hosts/VMs
- `analyze_performance_degradation` - Detect slowdowns
- `find_slow_queries` - Database query analysis
- `analyze_error_rates` - Error trends
- `calculate_uptime` - Availability metrics
- `get_infrastructure_health` - Overall health summary
- `check_alerts` - Current alert status

## Configuration

**Environment Variables:**
- `PROMETHEUS_URL` - Prometheus API URL (default: `http://10.0.121.218:9090`)
- `HOST` - HTTP server host (default: `0.0.0.0`)
- `PORT` - HTTP server port (default: `8000`)

## Deployment

### Docker Compose

```bash
cd examples/metrics-mcp
docker-compose up -d
```

Server will be accessible at:
- HTTP endpoint: `http://hostname:8084`
- SSE endpoint: `http://hostname:8084/sse`
- POST endpoint: `http://hostname:8084/`
- Health check: `http://hostname:8084/health`

### Local Development

```bash
pip install -r requirements.txt
python -m src.mcp_server.server
```

## Connecting Cursor to Remote Server

Update `C:\Users\Peter\.cursor\mcp.json`:

```json
{
  "mcpServers": {
    "metrics-mcp": {
      "url": "http://10.0.121.218:8084/sse"
    }
  }
}
```

For local testing:
```json
{
  "mcpServers": {
    "metrics-mcp": {
      "url": "http://localhost:8084/sse"
    }
  }
}
```

## Agent Query Examples

These examples show how AI agents can chain tools to answer complex questions:

### Example 1: "is CPU usage higher than normal in the past 20 minutes for sterianos?"

**Agent Flow:**
1. `discover_metrics` to find CPU metrics
2. `query_metrics(query="pve_node_cpu_usage", time_range="20m", labels={"node": "sterianos"})`
3. `detect_anomalies` with baseline comparison

**Result:** Returns whether current usage is anomalous compared to normal baseline

**Tool Chain:**
```json
// Step 1: Discover CPU metrics
{
  "tool": "discover_metrics"
}

// Step 2: Query CPU usage for sterianos
{
  "tool": "query_metrics",
  "arguments": {
    "query": "pve_node_cpu_usage",
    "time_range": "20m",
    "labels": {"node": "sterianos"}
  }
}

// Step 3: Detect anomalies
{
  "tool": "detect_anomalies",
  "arguments": {
    "query": "pve_node_cpu_usage",
    "time_range": "20m",
    "labels": {"node": "sterianos"},
    "baseline_range": "7d"
  }
}
```

### Example 2: "what has overall ram usage looked like on my entire proxmox cluster lately?"

**Agent Flow:**
1. `discover_metrics` to find memory metrics
2. `analyze_resource_utilization(resource_type="memory", time_range="7d", scope="cluster")`
3. `detect_trends` to show trend direction

**Result:** Returns cluster-wide RAM usage trends over time

**Tool Chain:**
```json
// Step 1: Discover memory metrics
{
  "tool": "discover_metrics"
}

// Step 2: Analyze cluster-wide memory utilization
{
  "tool": "analyze_resource_utilization",
  "arguments": {
    "resource_type": "memory",
    "time_range": "7d",
    "scope": "cluster"
  }
}

// Step 3: Detect trends
{
  "tool": "detect_trends",
  "arguments": {
    "query": "pve_node_memory_usage",
    "time_range": "7d"
  }
}
```

### Example 3: "is my zfs pool under stress lately?"

**Agent Flow:**
1. `discover_metrics` to find ZFS metrics (scale_monitoring_*io*)
2. `query_metrics` for ZFS IO/latency metrics with time_range="7d"
3. `identify_bottlenecks` to detect stress indicators

**Result:** Returns stress indicators (high IO, latency, etc.)

**Tool Chain:**
```json
// Step 1: Discover ZFS metrics
{
  "tool": "discover_metrics"
}

// Step 2: Query ZFS IO metrics
{
  "tool": "query_metrics",
  "arguments": {
    "query": "scale_monitoring_cgroup_*_io_*",
    "time_range": "7d"
  }
}

// Step 3: Identify bottlenecks
{
  "tool": "identify_bottlenecks",
  "arguments": {
    "time_range": "7d",
    "resource_types": ["disk"]
  }
}
```

### Example 4: "how are CPU temps changing in the past hour?"

**Agent Flow:**
1. `discover_metrics` to find temperature metrics
2. `query_metrics(query="*temp*", time_range="1h")`
3. `calculate_rate` or `detect_trends` for change analysis

**Result:** Returns rate of temperature change and trend direction

**Tool Chain:**
```json
// Step 1: Discover temperature metrics
{
  "tool": "discover_metrics"
}

// Step 2: Query temperature metrics
{
  "tool": "query_metrics",
  "arguments": {
    "query": "*temp*",
    "time_range": "1h"
  }
}

// Step 3: Calculate rate of change
{
  "tool": "calculate_rate",
  "arguments": {
    "query": "scale_monitoring_smart_log_smart_disktemp_*",
    "time_range": "1h"
  }
}

// Or detect trends
{
  "tool": "detect_trends",
  "arguments": {
    "query": "scale_monitoring_smart_log_smart_disktemp_*",
    "time_range": "1h"
  }
}
```

## PromQL Query Examples

The server accepts PromQL queries or metric names with label filters:

**Basic metric query:**
```promql
pve_node_cpu_usage
```

**With label filters:**
```promql
pve_node_cpu_usage{node="sterianos"}
```

**Rate calculation:**
```promql
rate(container_cpu_usage_seconds_total[5m])
```

**Aggregation:**
```promql
sum(pve_node_memory_usage) by (node)
```

## Time Range Format

Time ranges support relative formats:
- `"20m"` - 20 minutes
- `"1h"` - 1 hour
- `"7d"` - 7 days
- `"30d"` - 30 days

## Label Filtering

All tools support label filtering via the `labels` parameter:

```json
{
  "labels": {
    "node": "sterianos",
    "job": "proxmox"
  }
}
```

## Smart Metric Discovery

The server automatically groups metrics by:
- **Exporter**: Proxmox (pve_*), cAdvisor (container_*), TrueNAS (scale_monitoring_*), PostgreSQL (pg_*)
- **Category**: CPU, Memory, Disk, Network, Temperature, Errors
- **Resource Type**: Host/Node, VM, Container, Database

Use `recommend_metrics` with a task description to get filtered, relevant metrics:

```json
{
  "tool": "recommend_metrics",
  "arguments": {
    "task": "CPU usage problems"
  }
}
```

## Usage Examples

**Get resource usage:**
```json
{
  "tool": "get_resource_usage",
  "arguments": {
    "resource_type": "cpu",
    "time_range": "1h",
    "scope": "sterianos"
  }
}
```

**Detect trends:**
```json
{
  "tool": "detect_trends",
  "arguments": {
    "query": "pve_node_memory_usage",
    "time_range": "7d",
    "direction": "up"
  }
}
```

**Compare periods:**
```json
{
  "tool": "compare_periods",
  "arguments": {
    "query": "pve_node_cpu_usage",
    "current_range": "1d",
    "compare_to": "7d"
  }
}
```

**Get infrastructure health:**
```json
{
  "tool": "get_infrastructure_health",
  "arguments": {
    "scope": "cluster",
    "time_range": "1h"
  }
}
```

## Dependencies

- `mcp>=0.9.0` - MCP SDK
- `fastapi>=0.104.0` - HTTP server
- `uvicorn[standard]>=0.24.0` - ASGI server
- `pandas>=2.0.0` - Time series manipulation
- `numpy>=1.24.0` - Statistical calculations
- `scipy>=1.11.0` - Advanced stats, correlation, anomaly detection
- `statsmodels>=0.14.0` - Forecasting, trend analysis
- `prometheus-client>=0.19.0` - Prometheus API client
- `requests>=2.31.0` - HTTP client for Prometheus API

## Integration

The server is accessible via HTTP/SSE to:
- k3s cluster services
- Ray cluster
- Cursor and other MCP-compatible tools
- Any HTTP client that supports SSE

## Design Principles

1. **Follow notes-mcp pattern** - Same structure, HTTP/SSE, error handling
2. **Prometheus client abstraction** - Separate module for easy testing/mocking
3. **Analysis functions separate** - Reusable, testable analysis logic
4. **Structured tool responses** - All tools return JSON with consistent format
5. **Error handling** - Clear error messages for invalid queries, connection issues
6. **No data storage** - Pure query/analysis layer, all data from Prometheus
7. **Smart metric discovery** - Automatically discover and group metrics intelligently, filter by task relevance

## Key Features for Agent Queries

- All tools accept `time_range` parameter (relative: "20m", "1h", "7d" or absolute timestamps)
- All tools accept `labels` parameter for filtering (e.g., `{"node": "sterianos"}`, `{"job": "proxmox"}`)
- `query_metrics` can accept either PromQL query string OR metric name + label filters
- Tools can be chained: discover metrics → query with filters → analyze → compare
- Cluster-wide aggregation via `scope="cluster"` parameter

