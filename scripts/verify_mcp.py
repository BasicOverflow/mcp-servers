#!/usr/bin/env python3
"""Verify metrics-mcp Streamable HTTP against live Prometheus."""
from __future__ import annotations

import json
import urllib.request

URL = "http://127.0.0.1:8084/mcp"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-03-26",
}


def post(payload: dict, session: str | None = None):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(URL, data=data, headers=HEADERS, method="POST")
    if session:
        req.add_header("Mcp-Session-Id", session)
    with urllib.request.urlopen(req, timeout=90) as r:
        body = r.read().decode()
        sid = r.headers.get("Mcp-Session-Id")
        ctype = r.headers.get("Content-Type", "")
    if "event-stream" in ctype or body.startswith("event:") or body.startswith(":"):
        objs = []
        for line in body.splitlines():
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if chunk:
                    objs.append(json.loads(chunk))
        return (objs[-1] if objs else {"raw": body[:500]}), sid
    return json.loads(body), sid


def main() -> None:
    init, sid = post(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "verify", "version": "0.1"},
            },
        }
    )
    print("INIT", init.get("result", {}).get("serverInfo"), "session=", sid)
    try:
        post({"jsonrpc": "2.0", "method": "notifications/initialized"}, session=sid)
    except Exception as e:
        print("notif:", type(e).__name__, e)

    tools, _ = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, session=sid)
    names = sorted(t["name"] for t in tools.get("result", {}).get("tools", []))
    print("TOOLS", len(names))
    print(", ".join(names))

    def call(name: str, arguments: dict | None = None, id_: int = 10):
        res, _ = post(
            {
                "jsonrpc": "2.0",
                "id": id_,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            },
            session=sid,
        )
        if "error" in res:
            return {"rpc_error": res["error"]}
        content = res.get("result", {}).get("content", [])
        text = "".join(c.get("text", "") for c in content if c.get("type") == "text")
        try:
            return json.loads(text) if text else res.get("result")
        except Exception:
            return {"text": text[:800]}

    checks = [
        ("prometheus_health", {}),
        ("list_targets", {}),
        ("infra_overview", {}),
        ("down_targets", {}),
        ("zfs_pool_summary", {}),
        ("compare_hosts", {"metric": "cpu", "time_range": "1h"}),
        ("top_guests", {"resource": "cpu", "limit": 5}),
        ("run_recipe", {"recipe_id": "node_memory", "mode": "instant"}),
        ("query_instant", {"query": "up", "limit": 30}),
        ("series_stats", {"query": 'node_load1{job="node"}', "time_range": "1h"}),
    ]
    for i, (tool, args) in enumerate(checks, start=20):
        out = call(tool, args, id_=i)
        if isinstance(out, dict) and (out.get("error") or out.get("rpc_error")):
            print(f"FAIL {tool}: {out}")
            continue
        if tool == "prometheus_health":
            print("OK", tool, out)
        elif tool == "list_targets":
            print("OK", tool, {"up": out.get("up"), "total": out.get("total")})
        elif tool == "infra_overview":
            print(
                "OK",
                tool,
                {
                    "targets": out.get("targets"),
                    "cpu": len(out.get("node_cpu_busy_pct") or []),
                    "mem": len(out.get("node_memory_used_pct") or []),
                    "zfs_alloc": len(out.get("zfs_alloc_bytes") or []),
                },
            )
        elif tool == "down_targets":
            print("OK", tool, {"count": out.get("down_or_error")})
        elif tool == "zfs_pool_summary":
            print(
                "OK",
                tool,
                [
                    {
                        "labels": p.get("labels"),
                        "used_pct": round(p["used_pct"], 2) if p.get("used_pct") is not None else None,
                    }
                    for p in (out.get("pools") or [])[:6]
                ],
            )
        elif tool == "compare_hosts":
            print(
                "OK",
                tool,
                [
                    {
                        "host": (h.get("labels") or {}).get("host"),
                        "mean": round((h.get("stats") or {}).get("mean") or 0, 2),
                    }
                    for h in (out.get("hosts") or [])
                ],
            )
        elif tool == "top_guests":
            print(
                "OK",
                tool,
                [
                    {"id": (t.get("metric") or {}).get("id"), "value": t.get("value")}
                    for t in (out.get("top") or [])[:5]
                ],
            )
        elif tool == "run_recipe":
            print("OK", tool, {"n": len(out.get("data") or []), "query": out.get("query")})
        elif tool == "query_instant":
            print("OK", tool, {"series": out.get("series")})
        elif tool == "series_stats":
            print("OK", tool, {"n": len(out.get("series") or [])})
        else:
            print("OK", tool)


if __name__ == "__main__":
    main()
