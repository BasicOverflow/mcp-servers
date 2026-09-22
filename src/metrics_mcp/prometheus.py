"""Async Prometheus HTTP API client."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx

DEFAULT_URL = os.getenv("PROMETHEUS_URL", "http://127.0.0.1:9090")
TIMEOUT = float(os.getenv("PROMETHEUS_TIMEOUT", "30"))


def parse_duration(spec: str) -> timedelta:
    """Parse 15m / 1h / 7d / 2w into timedelta."""
    spec = spec.strip().lower()
    if not spec or spec[-1] not in "smhdw":
        raise ValueError(f"Invalid duration '{spec}' (use Ns/Nm/Nh/Nd/Nw)")
    n = int(spec[:-1])
    unit = spec[-1]
    return {
        "s": timedelta(seconds=n),
        "m": timedelta(minutes=n),
        "h": timedelta(hours=n),
        "d": timedelta(days=n),
        "w": timedelta(weeks=n),
    }[unit]


def range_bounds(time_range: str) -> tuple[float, float]:
    end = datetime.now(timezone.utc)
    start = end - parse_duration(time_range)
    return start.timestamp(), end.timestamp()


def pick_step(time_range: str) -> str:
    """Choose a scrape-friendly step from range length."""
    secs = parse_duration(time_range).total_seconds()
    if secs <= 3600:
        return "15s"
    if secs <= 86400:
        return "1m"
    if secs <= 7 * 86400:
        return "5m"
    return "15m"


class Prometheus:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or DEFAULT_URL).rstrip("/")

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{self.base_url}{path}", params=params or {})
            r.raise_for_status()
            payload = r.json()
            if payload.get("status") != "success":
                raise RuntimeError(payload.get("error") or payload)
            return payload["data"]

    async def instant(self, query: str, t: float | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"query": query}
        if t is not None:
            params["time"] = t
        data = await self._get("/api/v1/query", params)
        return data.get("result", [])

    async def range_query(
        self,
        query: str,
        time_range: str = "1h",
        step: str | None = None,
    ) -> list[dict[str, Any]]:
        start, end = range_bounds(time_range)
        data = await self._get(
            "/api/v1/query_range",
            {
                "query": query,
                "start": start,
                "end": end,
                "step": step or pick_step(time_range),
            },
        )
        return data.get("result", [])

    async def targets(self) -> dict[str, Any]:
        return await self._get("/api/v1/targets")

    async def metric_names(self) -> list[str]:
        data = await self._get("/api/v1/label/__name__/values")
        return list(data) if isinstance(data, list) else []

    async def label_values(self, label: str) -> list[str]:
        data = await self._get(f"/api/v1/label/{quote(label, safe='')}/values")
        return list(data) if isinstance(data, list) else []

    async def metadata(self, metric: str | None = None) -> dict[str, Any]:
        params = {"metric": metric} if metric else None
        return await self._get("/api/v1/metadata", params)

    async def series(self, match: list[str], time_range: str = "1h") -> list[dict[str, str]]:
        start, end = range_bounds(time_range)
        params: list[tuple[str, str]] = [("start", str(start)), ("end", str(end))]
        params.extend(("match[]", m) for m in match)
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{self.base_url}/api/v1/series", params=params)
            r.raise_for_status()
            payload = r.json()
            if payload.get("status") != "success":
                raise RuntimeError(payload.get("error") or payload)
            return payload.get("data", [])

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            ready = await client.get(f"{self.base_url}/-/ready")
            healthy = await client.get(f"{self.base_url}/-/healthy")
        return {
            "url": self.base_url,
            "ready": ready.status_code == 200,
            "healthy": healthy.status_code == 200,
            "checked_at": time.time(),
        }


prom = Prometheus()