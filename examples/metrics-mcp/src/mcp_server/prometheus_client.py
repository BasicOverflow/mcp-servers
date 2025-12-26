"""Prometheus API client for querying metrics."""

import os
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import requests


def get_prometheus_url() -> str:
    """Get Prometheus URL from environment variable."""
    return os.getenv("PROMETHEUS_URL", "http://10.0.121.218:9090")


def parse_time_range(time_range: str) -> tuple[datetime, datetime]:
    """Parse relative time range string to start and end times."""
    end_time = datetime.now()
    
    if time_range.endswith("m"):
        minutes = int(time_range[:-1])
        start_time = end_time - timedelta(minutes=minutes)
    elif time_range.endswith("h"):
        hours = int(time_range[:-1])
        start_time = end_time - timedelta(hours=hours)
    elif time_range.endswith("d"):
        days = int(time_range[:-1])
        start_time = end_time - timedelta(days=days)
    elif time_range.endswith("w"):
        weeks = int(time_range[:-1])
        start_time = end_time - timedelta(weeks=weeks)
    else:
        raise ValueError(f"Invalid time range format: {time_range}")
    
    return start_time, end_time


def build_promql_with_labels(query: str, labels: Optional[Dict[str, str]] = None) -> str:
    """Build PromQL query with label filters."""
    if not labels:
        return query
    
    label_filters = []
    for key, value in labels.items():
        label_filters.append(f'{key}="{value}"')
    
    if label_filters:
        if "{" in query:
            query = query.replace("}", f", {', '.join(label_filters)}}}")
        else:
            query = f"{query}{{{', '.join(label_filters)}}}"
    
    return query


def query_prometheus(query: str, time: Optional[str] = None, labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Execute PromQL instant query."""
    url = get_prometheus_url()
    query = build_promql_with_labels(query, labels)
    
    params = {"query": query}
    if time:
        params["time"] = time
    
    response = requests.get(f"{url}/api/v1/query", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def query_range(query: str, start: str, end: str, step: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Execute PromQL range query."""
    url = get_prometheus_url()
    query = build_promql_with_labels(query, labels)
    
    params = {
        "query": query,
        "start": start,
        "end": end,
        "step": step
    }
    
    response = requests.get(f"{url}/api/v1/query_range", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_metric_metadata() -> Dict[str, Any]:
    """Get metadata for all available metrics."""
    url = get_prometheus_url()
    response = requests.get(f"{url}/api/v1/metadata", timeout=30)
    response.raise_for_status()
    return response.json()


def get_all_metric_names() -> List[str]:
    """Get all metric names from Prometheus."""
    url = get_prometheus_url()
    response = requests.get(f"{url}/api/v1/label/__name__/values", timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get("data", [])


def get_label_values(label: str) -> List[str]:
    """Get all values for a specific label."""
    url = get_prometheus_url()
    response = requests.get(f"{url}/api/v1/label/{label}/values", timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get("data", [])

