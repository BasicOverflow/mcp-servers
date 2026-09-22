"""Lightweight numeric analysis over Prometheus range results (stdlib only)."""

from __future__ import annotations

import math
import statistics
from typing import Any


def _series_points(series: dict[str, Any]) -> tuple[list[float], list[float], dict[str, str]]:
    values = series.get("values") or []
    if not values and "value" in series:
        ts, val = series["value"]
        values = [[ts, val]]
    if not values:
        return [], [], dict(series.get("metric") or {})
    ts = [float(v[0]) for v in values]
    ys = [float(v[1]) for v in values]
    return ts, ys, dict(series.get("metric") or {})


def summarize_series(results: list[dict[str, Any]], max_series: int = 20) -> list[dict[str, Any]]:
    out = []
    for s in results[:max_series]:
        ts, ys, labels = _series_points(s)
        if not ys:
            continue
        out.append(
            {
                "labels": labels,
                "points": len(ys),
                "stats": _stats(ys),
                "latest": ys[-1],
                "first_ts": ts[0] if ts else None,
                "last_ts": ts[-1] if ts else None,
            }
        )
    return out


def _percentile(ys: list[float], p: float) -> float:
    if not ys:
        return float("nan")
    s = sorted(ys)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def _stats(ys: list[float]) -> dict[str, float]:
    return {
        "mean": float(statistics.fmean(ys)),
        "median": float(statistics.median(ys)),
        "min": float(min(ys)),
        "max": float(max(ys)),
        "std": float(statistics.pstdev(ys)) if len(ys) > 1 else 0.0,
        "p50": float(_percentile(ys, 50)),
        "p95": float(_percentile(ys, 95)),
        "p99": float(_percentile(ys, 99)),
    }


def _linear_fit(ys: list[float]) -> tuple[float, float]:
    """Return (slope, intercept) for y ~ slope*x + intercept, x = 0..n-1."""
    n = len(ys)
    if n < 2:
        return 0.0, ys[0] if ys else 0.0
    x_mean = (n - 1) / 2.0
    y_mean = statistics.fmean(ys)
    num = sum((i - x_mean) * (ys[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n)) or 1.0
    slope = num / den
    intercept = y_mean - slope * x_mean
    return slope, intercept


def detect_trend(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for s in results:
        ts, ys, labels = _series_points(s)
        if len(ys) < 5:
            out.append({"labels": labels, "trend": "insufficient_data"})
            continue
        slope, intercept = _linear_fit(ys)
        y_hat = [slope * i + intercept for i in range(len(ys))]
        ss_res = sum((ys[i] - y_hat[i]) ** 2 for i in range(len(ys)))
        y_mean = statistics.fmean(ys)
        ss_tot = sum((y - y_mean) ** 2 for y in ys) or 1.0
        r2 = 1.0 - ss_res / ss_tot
        direction = "up" if slope > 0 else "down" if slope < 0 else "flat"
        diffs = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
        step = float(statistics.median(diffs)) if diffs else 15.0
        per_hour = slope * (3600.0 / step) if step > 0 else slope
        mean = y_mean or 1.0
        out.append(
            {
                "labels": labels,
                "direction": direction,
                "slope_per_step": float(slope),
                "change_per_hour": float(per_hour),
                "change_per_hour_pct_of_mean": float(100.0 * per_hour / mean),
                "r_squared": float(r2),
                "latest": float(ys[-1]),
                "mean": mean,
            }
        )
    return out


def detect_anomalies(results: list[dict[str, Any]], z_thresh: float = 3.0) -> list[dict[str, Any]]:
    out = []
    for s in results:
        ts, ys, labels = _series_points(s)
        if len(ys) < 10:
            out.append({"labels": labels, "anomalies": [], "note": "insufficient_data"})
            continue
        mu = float(statistics.fmean(ys))
        sigma = float(statistics.pstdev(ys)) if len(ys) > 1 else 0.0
        if sigma == 0:
            out.append({"labels": labels, "anomalies": [], "mean": mu, "std": sigma})
            continue
        hits = []
        for i, y in enumerate(ys):
            zi = (y - mu) / sigma
            if abs(zi) >= z_thresh:
                hits.append({"ts": float(ts[i]), "value": float(y), "z": float(zi)})
        out.append(
            {
                "labels": labels,
                "mean": mu,
                "std": sigma,
                "z_threshold": z_thresh,
                "anomaly_count": len(hits),
                "anomalies": hits[:50],
            }
        )
    return out


def correlate_two(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> dict[str, Any]:
    """Pearson correlation on aligned timestamps of first series of each result."""
    if not a or not b:
        return {"error": "need data on both sides"}
    ts_a, ys_a, la = _series_points(a[0])
    ts_b, ys_b, lb = _series_points(b[0])
    if len(ys_a) < 5 or len(ys_b) < 5:
        return {"error": "insufficient_data", "labels_a": la, "labels_b": lb}
    paired_a: list[float] = []
    paired_b: list[float] = []
    j = 0
    for i, t in enumerate(ts_a):
        while j + 1 < len(ts_b) and abs(ts_b[j + 1] - t) < abs(ts_b[j] - t):
            j += 1
        if abs(ts_b[j] - t) <= 60:
            paired_a.append(ys_a[i])
            paired_b.append(ys_b[j])
    if len(paired_a) < 5:
        return {"error": "could_not_align", "labels_a": la, "labels_b": lb}
    if statistics.pstdev(paired_a) == 0 or statistics.pstdev(paired_b) == 0:
        corr = 0.0
    else:
        corr = float(statistics.correlation(paired_a, paired_b))
    return {
        "pearson_r": corr,
        "points_aligned": len(paired_a),
        "labels_a": la,
        "labels_b": lb,
        "interpretation": (
            "strong_positive"
            if corr >= 0.7
            else "moderate_positive"
            if corr >= 0.4
            else "weak"
            if corr > -0.4
            else "moderate_negative"
            if corr > -0.7
            else "strong_negative"
        ),
    }


def capacity_forecast(
    results: list[dict[str, Any]],
    threshold: float,
    horizon_hours: float = 168.0,
) -> list[dict[str, Any]]:
    out = []
    for s in results:
        ts, ys, labels = _series_points(s)
        if len(ys) < 8:
            out.append({"labels": labels, "status": "insufficient_data"})
            continue
        slope, _ = _linear_fit(ys)
        diffs = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
        step = float(statistics.median(diffs)) if diffs else 60.0
        latest = float(ys[-1])
        if slope <= 0:
            out.append(
                {
                    "labels": labels,
                    "status": "not_growing",
                    "latest": latest,
                    "threshold": threshold,
                    "slope_per_step": float(slope),
                }
            )
            continue
        steps_needed = (threshold - latest) / slope
        hours = (steps_needed * step) / 3600.0
        out.append(
            {
                "labels": labels,
                "status": "ok" if hours > 0 else "already_over",
                "latest": latest,
                "threshold": threshold,
                "eta_hours": float(hours) if hours > 0 else 0.0,
                "within_horizon": 0 < hours <= horizon_hours,
                "projected_in_horizon": float(latest + slope * (horizon_hours * 3600.0 / step)),
            }
        )
    return out


def format_instant(results: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    out = []
    for s in results[:limit]:
        metric = dict(s.get("metric") or {})
        if "value" in s:
            ts, val = s["value"]
            out.append({"metric": metric, "ts": float(ts), "value": float(val)})
        elif s.get("values"):
            ts, val = s["values"][-1]
            out.append({"metric": metric, "ts": float(ts), "value": float(val), "points": len(s["values"])})
    return out
