import argparse
import asyncio
import json
import os
import statistics
import time
from typing import Any, Dict, List, Tuple

import websockets


def build_ws_url(base_url: str, service_key: str, mime_type: str) -> str:
    base = base_url.rstrip("/")
    url = f"{base}/api/voice/stream?service_api_key={service_key}&mime_type={mime_type}"
    if url.startswith("https://"):
        url = "wss://" + url[len("https://") :]
    elif url.startswith("http://"):
        url = "ws://" + url[len("http://") :]
    return url


async def run_switch_sequence(
    ws_url: str,
    roles: List[str],
    iterations: int,
    delay_ms: int,
) -> Tuple[List[float], List[Dict[str, Any]]]:
    switch_latencies: List[float] = []
    raw_events: List[Dict[str, Any]] = []

    async with websockets.connect(ws_url) as ws:
        # Start session with first role
        first_role = roles[0]
        await ws.send(json.dumps({"type": "voice.start", "role_id": first_role, "mime_type": "audio/webm"}))

        # Wait for ack
        while True:
            message = await ws.recv()
            payload = json.loads(message)
            raw_events.append(payload)
            if payload.get("type") == "voice.ack":
                break

        for i in range(iterations):
            target_role = roles[(i + 1) % len(roles)]
            started = time.perf_counter()
            await ws.send(json.dumps({"type": "voice.switch", "role_id": target_role}))

            while True:
                message = await ws.recv()
                payload = json.loads(message)
                raw_events.append(payload)
                if payload.get("type") == "voice.role_status":
                    if payload.get("status") in {"active", "error"} and payload.get("role_id") == target_role:
                        latency = (time.perf_counter() - started) * 1000.0
                        switch_latencies.append(latency)
                        break
            await asyncio.sleep(delay_ms / 1000.0)

        await ws.send(json.dumps({"type": "voice.end"}))

    return switch_latencies, raw_events


def summarize_latency(values: List[float]) -> Dict[str, float]:
    if not values:
        return {}
    return {
        "min": min(values),
        "max": max(values),
        "avg": statistics.mean(values),
        "median": statistics.median(values),
        "p95": statistics.quantiles(values, n=100)[94] if len(values) >= 20 else max(values),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multirole gateway switch benchmark")
    parser.add_argument("--api-base", default=os.getenv("BENCH_API_BASE", "http://localhost:8000"), help="API base URL")
    parser.add_argument("--service-key", default=os.getenv("BENCH_SERVICE_KEY", ""), help="Service API key")
    parser.add_argument("--roles", default=os.getenv("BENCH_ROLES", "huangrong,xiaoruan,pipi"), help="Comma-separated roles")
    parser.add_argument("--iterations", type=int, default=int(os.getenv("BENCH_ITERATIONS", "20")))
    parser.add_argument("--delay-ms", type=int, default=int(os.getenv("BENCH_DELAY_MS", "200")))
    parser.add_argument("--mime-type", default=os.getenv("BENCH_MIME", "audio/webm"))
    parser.add_argument("--output", default="bench_results.json", help="File to store raw results")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ws_url = build_ws_url(args.api_base, args.service_key, args.mime_type)
    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    print(f"Connecting to {ws_url}")
    print(f"Switching between roles: {roles} ({args.iterations} iterations)")

    switch_latencies, events = asyncio.run(
        run_switch_sequence(ws_url=ws_url, roles=roles, iterations=args.iterations, delay_ms=args.delay_ms)
    )
    summary = summarize_latency(switch_latencies)
    success_count = sum(1 for e in events if e.get("type") == "voice.role_status" and e.get("status") == "active")
    error_count = sum(1 for e in events if e.get("type") == "voice.role_status" and e.get("status") == "error")

    result = {
        "switch_latencies_ms": switch_latencies,
        "summary": summary,
        "success_count": success_count,
        "error_count": error_count,
        "events": events,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("Summary:", json.dumps(summary, indent=2))
    print("Success:", success_count, "Errors:", error_count)
    print(f"Raw events stored in {args.output}")


if __name__ == "__main__":
    main()

