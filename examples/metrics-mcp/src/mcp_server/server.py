"""Metrics MCP server for Prometheus analysis."""

import json
import os
from typing import Optional, Dict, List, Any
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent

from .prometheus_client import (
    query_prometheus, query_range, get_metric_metadata,
    get_all_metric_names, get_label_values, parse_time_range
)
from .metric_discovery import (
    discover_all_metrics, get_metric_info, get_recommended_metrics,
    group_metrics_by_exporter, group_metrics_by_category, group_metrics_by_resource
)
from .metrics_analysis import (
    prometheus_to_dataframe, calculate_percentiles, calculate_statistics,
    calculate_rate, calculate_derivative, detect_trends, calculate_moving_average,
    forecast_capacity, detect_anomalies, compare_periods, calculate_growth_rate,
    find_peak_usage, correlate_metrics, compare_series, calculate_ratios
)


app = Server("metrics-mcp-server")


async def _get_tools_list() -> list[Tool]:
    """Get the list of available tools."""
    return [
        # Metric Discovery Tools
        Tool(
            name="discover_metrics",
            description="Discover all available metrics from Prometheus, returns grouped by exporter/category/resource",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_metric_info",
            description="Get detailed information about a specific metric (labels, type, help text)",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric_name": {
                        "type": "string",
                        "description": "Name of the metric to get info for"
                    }
                },
                "required": ["metric_name"]
            }
        ),
        Tool(
            name="recommend_metrics",
            description="Get recommended metrics for a task description (uses smart filtering)",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task description (e.g., 'CPU usage', 'memory problems')"
                    }
                },
                "required": ["task"]
            }
        ),
        # Time Series Operations
        Tool(
            name="query_metrics",
            description="Query Prometheus for specific metrics. Accepts PromQL query or metric name with optional label filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "PromQL query string or metric name"
                    },
                    "time_range": {
                        "type": "string",
                        "description": "Time range (e.g., '20m', '1h', '7d')"
                    },
                    "labels": {
                        "type": "object",
                        "description": "Label filters as key-value pairs (e.g., {'node': 'sterianos'})"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "Optional end time (ISO format or timestamp)"
                    }
                },
                "required": ["query", "time_range"]
            }
        ),
        Tool(
            name="calculate_percentiles",
            description="Calculate percentiles (p50, p95, p99) for a metric",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"},
                    "percentiles": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of percentiles to calculate (default: [50, 95, 99])"
                    }
                },
                "required": ["query", "time_range"]
            }
        ),
        Tool(
            name="calculate_statistics",
            description="Calculate basic statistics: mean, median, min, max, std dev",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"}
                },
                "required": ["query", "time_range"]
            }
        ),
        Tool(
            name="calculate_rate",
            description="Calculate rate of change (requests/sec, bytes/sec)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"},
                    "window": {"type": "string", "description": "Rate window (e.g., '5m')"}
                },
                "required": ["query", "time_range"]
            }
        ),
        Tool(
            name="calculate_derivative",
            description="Calculate rate of change over time",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"}
                },
                "required": ["query", "time_range"]
            }
        ),
        Tool(
            name="detect_trends",
            description="Detect upward/downward trends in time series",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"},
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "any"],
                        "description": "Filter by trend direction"
                    }
                },
                "required": ["query", "time_range"]
            }
        ),
        Tool(
            name="calculate_moving_average",
            description="Calculate moving average to smooth out noise (7-day, 30-day)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"},
                    "window": {"type": "string", "description": "Window size (e.g., '7d', '30d')"}
                },
                "required": ["query", "time_range"]
            }
        ),
        Tool(
            name="forecast_capacity",
            description="Project future usage based on historical trends",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"},
                    "forecast_period": {"type": "string", "description": "Forecast period (e.g., '7d')"}
                },
                "required": ["query", "time_range"]
            }
        ),
        Tool(
            name="detect_anomalies",
            description="Detect statistical outliers (compares to baseline)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"},
                    "baseline_range": {"type": "string", "description": "Baseline period (e.g., '7d')"}
                },
                "required": ["query", "time_range"]
            }
        ),
        Tool(
            name="compare_periods",
            description="Compare two time periods (week-over-week, month-over-month)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "current_range": {"type": "string"},
                    "labels": {"type": "object"},
                    "compare_to": {"type": "string", "description": "Period to compare (e.g., '7d' for week-over-week)"}
                },
                "required": ["query", "current_range"]
            }
        ),
        Tool(
            name="calculate_growth_rate",
            description="Calculate percentage change/growth rate",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"}
                },
                "required": ["query", "time_range"]
            }
        ),
        Tool(
            name="find_peak_usage",
            description="Identify peak times/days",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"}
                },
                "required": ["query", "time_range"]
            }
        ),
        # Multi-Series Operations
        Tool(
            name="correlate_metrics",
            description="Find relationships between metrics (e.g., CPU vs memory)",
            inputSchema={
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of PromQL queries or metric names"
                    },
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"}
                },
                "required": ["queries", "time_range"]
            }
        ),
        Tool(
            name="compare_series",
            description="Side-by-side comparison of multiple metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"}
                },
                "required": ["queries", "time_range"]
            }
        ),
        Tool(
            name="calculate_ratios",
            description="Calculate efficiency metrics (ratios)",
            inputSchema={
                "type": "object",
                "properties": {
                    "numerator_query": {"type": "string"},
                    "denominator_query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"}
                },
                "required": ["numerator_query", "denominator_query", "time_range"]
            }
        ),
        Tool(
            name="analyze_resource_utilization",
            description="Analyze CPU/RAM/disk across hosts. Supports cluster-wide aggregation",
            inputSchema={
                "type": "object",
                "properties": {
                    "resource_type": {
                        "type": "string",
                        "enum": ["cpu", "memory", "disk"],
                        "description": "Type of resource to analyze"
                    },
                    "time_range": {"type": "string"},
                    "scope": {
                        "type": "string",
                        "description": "Scope: 'cluster', 'node', or specific node name"
                    }
                },
                "required": ["resource_type", "time_range"]
            }
        ),
        Tool(
            name="identify_bottlenecks",
            description="Find constrained resources/bottlenecks",
            inputSchema={
                "type": "object",
                "properties": {
                    "time_range": {"type": "string"},
                    "scope": {"type": "string"},
                    "resource_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of resource types to check"
                    }
                },
                "required": ["time_range"]
            }
        ),
        Tool(
            name="project_capacity_needs",
            description="Forecast when resources will be exhausted",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"},
                    "threshold": {"type": "number", "description": "Threshold percentage"}
                },
                "required": ["query", "time_range"]
            }
        ),
        Tool(
            name="analyze_resource_distribution",
            description="Analyze resource balance across cluster",
            inputSchema={
                "type": "object",
                "properties": {
                    "resource_type": {"type": "string"},
                    "time_range": {"type": "string"},
                    "scope": {"type": "string"}
                },
                "required": ["resource_type", "time_range"]
            }
        ),
        # Infrastructure Insights
        Tool(
            name="get_resource_usage",
            description="Get CPU/RAM/disk usage for hosts/VMs",
            inputSchema={
                "type": "object",
                "properties": {
                    "resource_type": {
                        "type": "string",
                        "enum": ["cpu", "memory", "disk"]
                    },
                    "time_range": {"type": "string"},
                    "scope": {"type": "string"}
                },
                "required": ["resource_type", "time_range"]
            }
        ),
        Tool(
            name="analyze_performance_degradation",
            description="Detect slowdowns/performance degradation",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"},
                    "baseline_range": {"type": "string"}
                },
                "required": ["query", "time_range"]
            }
        ),
        Tool(
            name="find_slow_queries",
            description="Find slow database queries",
            inputSchema={
                "type": "object",
                "properties": {
                    "database_type": {
                        "type": "string",
                        "enum": ["postgres", "mongodb"]
                    },
                    "time_range": {"type": "string"},
                    "threshold": {"type": "string", "description": "Duration threshold"}
                },
                "required": ["database_type", "time_range"]
            }
        ),
        Tool(
            name="analyze_error_rates",
            description="Analyze error trends and patterns",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"}
                },
                "required": ["query", "time_range"]
            }
        ),
        Tool(
            name="calculate_uptime",
            description="Calculate availability/uptime metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Host/service name"},
                    "time_range": {"type": "string"},
                    "labels": {"type": "object"}
                },
                "required": ["target", "time_range"]
            }
        ),
        Tool(
            name="get_infrastructure_health",
            description="Get overall infrastructure health summary",
            inputSchema={
                "type": "object",
                "properties": {
                    "scope": {"type": "string"},
                    "time_range": {"type": "string"}
                },
                "required": []
            }
        ),
        Tool(
            name="check_alerts",
            description="Check current alert status",
            inputSchema={
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "warning", "all"]
                    },
                    "labels": {"type": "object"}
                },
                "required": []
            }
        )
    ]


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return await _get_tools_list()


async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "discover_metrics":
        all_metrics = discover_all_metrics()
        by_exporter = group_metrics_by_exporter(all_metrics)
        by_category = group_metrics_by_category(all_metrics)
        by_resource = group_metrics_by_resource(all_metrics)
        
        result = {
            "total_metrics": len(all_metrics),
            "by_exporter": by_exporter,
            "by_category": by_category,
            "by_resource": by_resource
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "get_metric_info":
        metric_name = arguments.get("metric_name")
        info = get_metric_info(metric_name)
        return [TextContent(type="text", text=json.dumps(info, indent=2))]
    
    elif name == "recommend_metrics":
        task = arguments.get("task")
        result = get_recommended_metrics(task)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "query_metrics":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        end_time = arguments.get("end_time")
        
        start_time, end = parse_time_range(time_range)
        start_str = start_time.isoformat()
        end_str = end.isoformat() if not end_time else end_time
        
        result = query_range(query, start_str, end_str, "15s", labels)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "calculate_percentiles":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        percentiles = arguments.get("percentiles", [50, 95, 99])
        
        start_time, end_time = parse_time_range(time_range)
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        percentiles_result = calculate_percentiles(df, percentiles)
        return [TextContent(type="text", text=json.dumps(percentiles_result, indent=2))]
    
    elif name == "calculate_statistics":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        
        start_time, end_time = parse_time_range(time_range)
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        stats_result = calculate_statistics(df)
        return [TextContent(type="text", text=json.dumps(stats_result, indent=2))]
    
    elif name == "calculate_rate":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        window = arguments.get("window", "5m")
        
        start_time, end_time = parse_time_range(time_range)
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        df_with_rate = calculate_rate(df, window)
        rate_data = df_with_rate[["rate"]].to_dict() if "rate" in df_with_rate.columns else {}
        return [TextContent(type="text", text=json.dumps(rate_data, indent=2, default=str))]
    
    elif name == "calculate_derivative":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        
        start_time, end_time = parse_time_range(time_range)
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        df_deriv = calculate_derivative(df)
        deriv_data = df_deriv.to_dict() if not df_deriv.empty else {}
        return [TextContent(type="text", text=json.dumps(deriv_data, indent=2, default=str))]
    
    elif name == "detect_trends":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        direction = arguments.get("direction")
        
        start_time, end_time = parse_time_range(time_range)
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        trends_result = detect_trends(df, direction)
        return [TextContent(type="text", text=json.dumps(trends_result, indent=2))]
    
    elif name == "calculate_moving_average":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        window = arguments.get("window", "7d")
        
        start_time, end_time = parse_time_range(time_range)
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        df_ma = calculate_moving_average(df, window)
        ma_data = df_ma[["moving_avg"]].to_dict() if "moving_avg" in df_ma.columns else {}
        return [TextContent(type="text", text=json.dumps(ma_data, indent=2, default=str))]
    
    elif name == "forecast_capacity":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        forecast_period = arguments.get("forecast_period", "7d")
        
        start_time, end_time = parse_time_range(time_range)
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        forecast_result = forecast_capacity(df, forecast_period)
        return [TextContent(type="text", text=json.dumps(forecast_result, indent=2))]
    
    elif name == "detect_anomalies":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        baseline_range = arguments.get("baseline_range")
        
        start_time, end_time = parse_time_range(time_range)
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        
        baseline_df = None
        if baseline_range:
            baseline_start, baseline_end = parse_time_range(baseline_range)
            baseline_result = query_range(query, baseline_start.isoformat(), baseline_end.isoformat(), "15s", labels)
            baseline_df = prometheus_to_dataframe(baseline_result)
        
        anomalies_result = detect_anomalies(df, baseline_df)
        return [TextContent(type="text", text=json.dumps(anomalies_result, indent=2))]
    
    elif name == "compare_periods":
        query = arguments.get("query")
        current_range = arguments.get("current_range")
        labels = arguments.get("labels")
        compare_to = arguments.get("compare_to", "7d")
        
        current_start, current_end = parse_time_range(current_range)
        current_result = query_range(query, current_start.isoformat(), current_end.isoformat(), "15s", labels)
        current_df = prometheus_to_dataframe(current_result)
        
        compare_start, compare_end = parse_time_range(compare_to)
        compare_result = query_range(query, compare_start.isoformat(), compare_end.isoformat(), "15s", labels)
        compare_df = prometheus_to_dataframe(compare_result)
        
        comparison = compare_periods(current_df, compare_df)
        return [TextContent(type="text", text=json.dumps(comparison, indent=2))]
    
    elif name == "calculate_growth_rate":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        
        start_time, end_time = parse_time_range(time_range)
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        growth_result = calculate_growth_rate(df)
        return [TextContent(type="text", text=json.dumps(growth_result, indent=2))]
    
    elif name == "find_peak_usage":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        
        start_time, end_time = parse_time_range(time_range)
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        peak_result = find_peak_usage(df)
        return [TextContent(type="text", text=json.dumps(peak_result, indent=2))]
    
    elif name == "correlate_metrics":
        queries = arguments.get("queries")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        
        if len(queries) < 2:
            return [TextContent(type="text", text=json.dumps({"error": "Need at least 2 queries"}, indent=2))]
        
        start_time, end_time = parse_time_range(time_range)
        
        df1_result = query_range(queries[0], start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df1 = prometheus_to_dataframe(df1_result)
        
        df2_result = query_range(queries[1], start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df2 = prometheus_to_dataframe(df2_result)
        
        correlation = correlate_metrics(df1, df2)
        return [TextContent(type="text", text=json.dumps(correlation, indent=2))]
    
    elif name == "compare_series":
        queries = arguments.get("queries")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        
        start_time, end_time = parse_time_range(time_range)
        df_list = []
        
        for query in queries:
            result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
            df = prometheus_to_dataframe(result)
            df_list.append(df)
        
        comparison = compare_series(df_list)
        return [TextContent(type="text", text=json.dumps(comparison, indent=2))]
    
    elif name == "calculate_ratios":
        numerator_query = arguments.get("numerator_query")
        denominator_query = arguments.get("denominator_query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        
        start_time, end_time = parse_time_range(time_range)
        
        num_result = query_range(numerator_query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        num_df = prometheus_to_dataframe(num_result)
        
        den_result = query_range(denominator_query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        den_df = prometheus_to_dataframe(den_result)
        
        ratios_df = calculate_ratios(num_df, den_df)
        ratios_data = ratios_df.to_dict() if not ratios_df.empty else {}
        return [TextContent(type="text", text=json.dumps(ratios_data, indent=2, default=str))]
    
    elif name == "analyze_resource_utilization":
        resource_type = arguments.get("resource_type")
        time_range = arguments.get("time_range")
        scope = arguments.get("scope", "cluster")
        
        start_time, end_time = parse_time_range(time_range)
        
        if resource_type == "cpu":
            query = "pve_node_cpu_usage" if scope == "cluster" else f"pve_node_cpu_usage{{node=\"{scope}\"}}"
        elif resource_type == "memory":
            query = "pve_node_memory_usage" if scope == "cluster" else f"pve_node_memory_usage{{node=\"{scope}\"}}"
        elif resource_type == "disk":
            query = "pve_node_disk_usage" if scope == "cluster" else f"pve_node_disk_usage{{node=\"{scope}\"}}"
        else:
            return [TextContent(type="text", text=json.dumps({"error": "Invalid resource_type"}, indent=2))]
        
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s")
        df = prometheus_to_dataframe(result)
        stats_result = calculate_statistics(df)
        
        return [TextContent(type="text", text=json.dumps({"resource_type": resource_type, "scope": scope, "statistics": stats_result}, indent=2))]
    
    elif name == "identify_bottlenecks":
        time_range = arguments.get("time_range")
        scope = arguments.get("scope")
        resource_types = arguments.get("resource_types", ["cpu", "memory", "disk"])
        
        start_time, end_time = parse_time_range(time_range)
        bottlenecks = []
        
        for resource_type in resource_types:
            if resource_type == "cpu":
                query = "pve_node_cpu_usage"
            elif resource_type == "memory":
                query = "pve_node_memory_usage"
            elif resource_type == "disk":
                query = "pve_node_disk_usage"
            else:
                continue
            
            labels = {"node": scope} if scope and scope != "cluster" else None
            result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
            df = prometheus_to_dataframe(result)
            
            if not df.empty:
                stats = calculate_statistics(df)
                if stats.get("mean", 0) > 80:
                    bottlenecks.append({
                        "resource": resource_type,
                        "utilization": stats.get("mean"),
                        "status": "high"
                    })
        
        return [TextContent(type="text", text=json.dumps({"bottlenecks": bottlenecks}, indent=2))]
    
    elif name == "project_capacity_needs":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        threshold = arguments.get("threshold", 90)
        
        start_time, end_time = parse_time_range(time_range)
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        forecast_result = forecast_capacity(df, "7d")
        
        if forecast_result.get("projected_value"):
            projected = forecast_result["projected_value"]
            if projected >= threshold:
                forecast_result["capacity_warning"] = True
                forecast_result["threshold_exceeded"] = projected >= threshold
        
        return [TextContent(type="text", text=json.dumps(forecast_result, indent=2))]
    
    elif name == "analyze_resource_distribution":
        resource_type = arguments.get("resource_type")
        time_range = arguments.get("time_range")
        scope = arguments.get("scope", "cluster")
        
        start_time, end_time = parse_time_range(time_range)
        
        if resource_type == "cpu":
            query = "pve_node_cpu_usage"
        elif resource_type == "memory":
            query = "pve_node_memory_usage"
        elif resource_type == "disk":
            query = "pve_node_disk_usage"
        else:
            return [TextContent(type="text", text=json.dumps({"error": "Invalid resource_type"}, indent=2))]
        
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s")
        df = prometheus_to_dataframe(result)
        
        if not df.empty and "node" in df.columns:
            distribution = df.groupby("node")["value"].mean().to_dict()
            return [TextContent(type="text", text=json.dumps({"distribution": distribution}, indent=2, default=str))]
        
        return [TextContent(type="text", text=json.dumps({"distribution": {}}, indent=2))]
    
    elif name == "get_resource_usage":
        resource_type = arguments.get("resource_type")
        time_range = arguments.get("time_range")
        scope = arguments.get("scope")
        
        start_time, end_time = parse_time_range(time_range)
        
        if resource_type == "cpu":
            query = "pve_node_cpu_usage"
        elif resource_type == "memory":
            query = "pve_node_memory_usage"
        elif resource_type == "disk":
            query = "pve_node_disk_usage"
        else:
            return [TextContent(type="text", text=json.dumps({"error": "Invalid resource_type"}, indent=2))]
        
        labels = {"node": scope} if scope and scope != "cluster" else None
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        stats_result = calculate_statistics(df)
        
        return [TextContent(type="text", text=json.dumps({"resource_type": resource_type, "scope": scope, "usage": stats_result}, indent=2))]
    
    elif name == "analyze_performance_degradation":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        baseline_range = arguments.get("baseline_range")
        
        start_time, end_time = parse_time_range(time_range)
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        
        baseline_df = None
        if baseline_range:
            baseline_start, baseline_end = parse_time_range(baseline_range)
            baseline_result = query_range(query, baseline_start.isoformat(), baseline_end.isoformat(), "15s", labels)
            baseline_df = prometheus_to_dataframe(baseline_result)
        
        current_stats = calculate_statistics(df)
        baseline_stats = calculate_statistics(baseline_df) if baseline_df is not None else {}
        
        degradation = {}
        if baseline_stats:
            current_mean = current_stats.get("mean", 0)
            baseline_mean = baseline_stats.get("mean", 0)
            if baseline_mean > 0:
                degradation["percent_change"] = ((current_mean - baseline_mean) / baseline_mean) * 100
                degradation["degraded"] = degradation["percent_change"] < -10
        
        return [TextContent(type="text", text=json.dumps({"current": current_stats, "baseline": baseline_stats, "degradation": degradation}, indent=2))]
    
    elif name == "find_slow_queries":
        database_type = arguments.get("database_type")
        time_range = arguments.get("time_range")
        threshold = arguments.get("threshold", "1s")
        
        start_time, end_time = parse_time_range(time_range)
        
        if database_type == "postgres":
            query = "pg_stat_statements_mean_exec_time"
        elif database_type == "mongodb":
            query = "mongodb_op_latencies_latency"
        else:
            return [TextContent(type="text", text=json.dumps({"error": "Unsupported database type"}, indent=2))]
        
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s")
        df = prometheus_to_dataframe(result)
        
        if not df.empty:
            slow_queries = df[df["value"] > float(threshold.replace("s", "").replace("ms", ""))]
            slow_list = slow_queries.to_dict("records") if not slow_queries.empty else []
            return [TextContent(type="text", text=json.dumps({"slow_queries": slow_list}, indent=2, default=str))]
        
        return [TextContent(type="text", text=json.dumps({"slow_queries": []}, indent=2))]
    
    elif name == "analyze_error_rates":
        query = arguments.get("query")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        
        start_time, end_time = parse_time_range(time_range)
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        
        stats_result = calculate_statistics(df)
        trends_result = detect_trends(df)
        
        return [TextContent(type="text", text=json.dumps({"statistics": stats_result, "trends": trends_result}, indent=2))]
    
    elif name == "calculate_uptime":
        target = arguments.get("target")
        time_range = arguments.get("time_range")
        labels = arguments.get("labels")
        
        start_time, end_time = parse_time_range(time_range)
        query = f"up{{instance=\"{target}\"}}"
        
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s", labels)
        df = prometheus_to_dataframe(result)
        
        if not df.empty:
            uptime_pct = (df["value"].sum() / len(df)) * 100
            return [TextContent(type="text", text=json.dumps({"target": target, "uptime_percent": uptime_pct}, indent=2))]
        
        return [TextContent(type="text", text=json.dumps({"target": target, "uptime_percent": 0}, indent=2))]
    
    elif name == "get_infrastructure_health":
        scope = arguments.get("scope", "all")
        time_range = arguments.get("time_range", "1h")
        
        start_time, end_time = parse_time_range(time_range)
        
        health = {
            "scope": scope,
            "time_range": time_range,
            "status": "healthy",
            "checks": []
        }
        
        query = "up"
        result = query_range(query, start_time.isoformat(), end_time.isoformat(), "15s")
        df = prometheus_to_dataframe(result)
        
        if not df.empty:
            avg_up = df["value"].mean()
            health["availability"] = float(avg_up * 100)
            health["status"] = "healthy" if avg_up > 0.95 else "degraded"
        
        return [TextContent(type="text", text=json.dumps(health, indent=2))]
    
    elif name == "check_alerts":
        severity = arguments.get("severity", "all")
        labels = arguments.get("labels")
        
        query = "ALERTS"
        result = query_prometheus(query)
        
        alerts = []
        if result.get("status") == "success":
            data = result.get("data", {})
            for item in data.get("result", []):
                alert_labels = item.get("metric", {})
                if severity != "all" and alert_labels.get("severity") != severity:
                    continue
                alerts.append(alert_labels)
        
        return [TextContent(type="text", text=json.dumps({"alerts": alerts, "count": len(alerts)}, indent=2))]
    
    else:
        raise ValueError(f"Unknown tool: {name}")


def main():
    """Run the MCP server in HTTP mode."""
    import uvicorn
    from .http_server import http_app
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    uvicorn.run(
        "src.mcp_server.http_server:http_app",
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()

