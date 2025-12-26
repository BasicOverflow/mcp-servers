"""Smart metric discovery and grouping."""

from typing import Dict, List, Any, Optional
from .prometheus_client import get_all_metric_names, get_metric_metadata, get_label_values


def discover_all_metrics() -> List[str]:
    """Query Prometheus for all available metrics."""
    return get_all_metric_names()


def group_metrics_by_exporter(metrics: List[str]) -> Dict[str, List[str]]:
    """Group metrics by exporter type using pattern matching."""
    groups: Dict[str, List[str]] = {
        "proxmox": [],
        "cadvisor": [],
        "truenas": [],
        "postgres": [],
        "mongodb": [],
        "node_exporter": [],
        "other": []
    }
    
    for metric in metrics:
        if metric.startswith("pve_"):
            groups["proxmox"].append(metric)
        elif metric.startswith("container_"):
            groups["cadvisor"].append(metric)
        elif metric.startswith("scale_monitoring_"):
            groups["truenas"].append(metric)
        elif metric.startswith("pg_") or metric.startswith("postgres_"):
            groups["postgres"].append(metric)
        elif metric.startswith("mongodb_") or metric.startswith("mongo_"):
            groups["mongodb"].append(metric)
        elif metric.startswith("node_"):
            groups["node_exporter"].append(metric)
        else:
            groups["other"].append(metric)
    
    return {k: v for k, v in groups.items() if v}


def group_metrics_by_category(metrics: List[str]) -> Dict[str, List[str]]:
    """Group metrics by category using keyword matching."""
    categories: Dict[str, List[str]] = {
        "cpu": [],
        "memory": [],
        "disk": [],
        "network": [],
        "temperature": [],
        "errors": [],
        "other": []
    }
    
    metric_lower = {}
    for metric in metrics:
        metric_lower[metric] = metric.lower()
    
    for metric, metric_low in metric_lower.items():
        if any(kw in metric_low for kw in ["cpu", "load"]):
            categories["cpu"].append(metric)
        elif any(kw in metric_low for kw in ["memory", "ram", "mem"]):
            categories["memory"].append(metric)
        elif any(kw in metric_low for kw in ["disk", "io", "storage", "filesystem", "fs"]):
            categories["disk"].append(metric)
        elif any(kw in metric_low for kw in ["network", "net", "rx", "tx", "bytes", "packets"]):
            categories["network"].append(metric)
        elif any(kw in metric_low for kw in ["temp", "temperature"]):
            categories["temperature"].append(metric)
        elif any(kw in metric_low for kw in ["error", "fail", "down", "unavailable"]):
            categories["errors"].append(metric)
        else:
            categories["other"].append(metric)
    
    return {k: v for k, v in categories.items() if v}


def group_metrics_by_resource(metrics: List[str]) -> Dict[str, List[str]]:
    """Group metrics by resource type using pattern matching."""
    resources: Dict[str, List[str]] = {
        "host": [],
        "vm": [],
        "container": [],
        "database": [],
        "other": []
    }
    
    for metric in metrics:
        if "node" in metric.lower() and not "vm" in metric.lower():
            resources["host"].append(metric)
        elif "vm" in metric.lower() or metric.startswith("pve_vm_"):
            resources["vm"].append(metric)
        elif metric.startswith("container_"):
            resources["container"].append(metric)
        elif any(kw in metric.lower() for kw in ["pg_", "postgres", "mongodb", "mongo", "database"]):
            resources["database"].append(metric)
        else:
            resources["other"].append(metric)
    
    return {k: v for k, v in resources.items() if v}


def filter_metrics_by_task(metrics: List[str], task_description: str) -> List[str]:
    """Filter metrics based on task description using keyword matching."""
    task_lower = task_description.lower()
    keywords = task_lower.split()
    
    scored_metrics: Dict[str, int] = {}
    
    for metric in metrics:
        metric_lower = metric.lower()
        score = 0
        
        for keyword in keywords:
            if keyword in metric_lower:
                if metric_lower.startswith(keyword) or metric_lower.endswith(keyword):
                    score += 3
                else:
                    score += 1
        
        if score > 0:
            scored_metrics[metric] = score
    
    sorted_metrics = sorted(scored_metrics.items(), key=lambda x: x[1], reverse=True)
    return [metric for metric, _ in sorted_metrics[:20]]


def get_recommended_metrics(task: str) -> Dict[str, Any]:
    """Get recommended metrics for a task with smart grouping."""
    all_metrics = discover_all_metrics()
    
    by_exporter = group_metrics_by_exporter(all_metrics)
    by_category = group_metrics_by_category(all_metrics)
    by_resource = group_metrics_by_resource(all_metrics)
    
    filtered = filter_metrics_by_task(all_metrics, task)
    
    return {
        "exporter": by_exporter,
        "category": by_category,
        "resource": by_resource,
        "recommended": filtered
    }


def get_metric_info(metric_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific metric."""
    metadata = get_metric_metadata()
    
    metric_info = {
        "name": metric_name,
        "type": None,
        "help": None,
        "labels": []
    }
    
    if "data" in metadata:
        if metric_name in metadata["data"]:
            metric_data = metadata["data"][metric_name]
            if metric_data:
                first_entry = metric_data[0]
                metric_info["type"] = first_entry.get("type")
                metric_info["help"] = first_entry.get("help")
    
    try:
        label_values = get_label_values("instance")
        metric_info["labels"] = ["instance", "job"]
    except:
        pass
    
    return metric_info

