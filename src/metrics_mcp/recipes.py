"""Built-in PromQL recipes for common node / PVE / ZFS exporters."""

from __future__ import annotations

RECIPES: dict[str, dict[str, str]] = {
    "node_cpu": {
        "title": "Host CPU busy %",
        "query": '100 * (1 - avg by (host) (rate(node_cpu_seconds_total{job="node",mode="idle"}[5m])))',
    },
    "node_memory": {
        "title": "Host memory used %",
        "query": '100 * (1 - node_memory_MemAvailable_bytes{job="node"} / node_memory_MemTotal_bytes{job="node"})',
    },
    "node_load": {
        "title": "Host load1",
        "query": 'node_load1{job="node"}',
    },
    "node_disk": {
        "title": "Root filesystem used %",
        "query": '100 * (1 - node_filesystem_avail_bytes{job="node",mountpoint="/",fstype!="rootfs"} / node_filesystem_size_bytes{job="node",mountpoint="/",fstype!="rootfs"})',
    },
    "pve_guest_cpu": {
        "title": "Guest CPU usage ratio (PVE exporter)",
        "query": 'pve_cpu_usage_ratio{id=~"qemu/.+|lxc/.+"}',
    },
    "pve_guest_mem": {
        "title": "Guest memory usage bytes",
        "query": 'pve_memory_usage_bytes{id=~"qemu/.+|lxc/.+"}',
    },
    "pve_up": {
        "title": "PVE guest/node up",
        "query": "pve_up",
    },
    "targets_up": {
        "title": "Scrape target up",
        "query": "up",
    },
    "truenas_smart_temp": {
        "title": "TrueNAS SMART disk temperatures",
        "query": '{job="truenas",__name__=~"scale_monitoring_smart_log_smart_disktemp_.*"}',
    },
    "zfs_alloc": {
        "title": "ZFS pool allocated bytes",
        "query": 'zfsprom_alloc{type="pool"}',
    },
    "zfs_free": {
        "title": "ZFS pool free bytes",
        "query": 'zfsprom_free{type="pool"}',
    },
    "zfs_capacity": {
        "title": "ZFS pool capacity (alloc+free)",
        "query": 'zfsprom_alloc{type="pool"} + zfsprom_free{type="pool"}',
    },
}

TASK_HINTS: list[tuple[list[str], list[str]]] = [
    (["cpu", "processor", "load"], ["node_cpu", "node_load", "pve_guest_cpu"]),
    (["mem", "memory", "ram"], ["node_memory", "pve_guest_mem"]),
    (["disk", "filesystem", "storage", "space"], ["node_disk", "zfs_alloc", "zfs_free", "zfs_capacity"]),
    (["zfs", "pool", "truenas", "nas"], ["zfs_alloc", "zfs_free", "zfs_capacity", "truenas_smart_temp"]),
    (["temp", "smart", "thermal"], ["truenas_smart_temp"]),
    (["guest", "vm", "lxc", "proxmox", "pve"], ["pve_guest_cpu", "pve_guest_mem", "pve_up"]),
    (["down", "health", "up", "target", "scrape"], ["targets_up", "pve_up"]),
]


def suggest_for_task(task: str) -> list[dict[str, str]]:
    t = task.lower()
    keys: list[str] = []
    for words, recipe_keys in TASK_HINTS:
        if any(w in t for w in words):
            for k in recipe_keys:
                if k not in keys:
                    keys.append(k)
    if not keys:
        keys = ["targets_up", "node_cpu", "node_memory", "zfs_alloc"]
    return [{"id": k, **RECIPES[k]} for k in keys if k in RECIPES]