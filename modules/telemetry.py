import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:  # pragma: no cover - optional dependency
    httpx = None  # type: ignore

logger = logging.getLogger("telemetry")


class TelemetryClient:
    def __init__(self) -> None:
        self.supabase_url = os.getenv("OBS_SUPABASE_URL")
        self.supabase_service_key = os.getenv("OBS_SUPABASE_SERVICE_KEY")
        self.metrics_table = os.getenv("OBS_METRICS_TABLE", "voice_metrics")
        self.sessions_table = os.getenv("OBS_SESSIONS_TABLE", "voice_sessions")
        self.role_switch_table = os.getenv("OBS_ROLE_SWITCH_TABLE", "voice_role_switches")
        self.enabled = bool(self.supabase_url and self.supabase_service_key and httpx is not None)
        self.queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None
        self.batch_size = int(os.getenv("OBS_BATCH_SIZE", "25"))
        self.batch_interval = float(os.getenv("OBS_BATCH_INTERVAL", "2.0"))
        self._last_flush = time.monotonic()

    async def start(self) -> None:
        if self.worker_task is None:
            self.worker_task = asyncio.create_task(self._worker(), name="telemetry-worker")
            logger.info("Telemetry client started (enabled=%s)", self.enabled)

    async def stop(self) -> None:
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            self.worker_task = None
        await self._drain_queue()

    async def record_metric(self, payload: Dict[str, Any]) -> None:
        await self.queue.put({"kind": "metric", "payload": payload})

    async def record_session(self, payload: Dict[str, Any]) -> None:
        await self.queue.put({"kind": "session", "payload": payload})

    async def record_role_switch(self, payload: Dict[str, Any]) -> None:
        await self.queue.put({"kind": "role_switch", "payload": payload})

    async def flush(self) -> None:
        await self._drain_queue()

    async def _worker(self) -> None:
        batch: List[Dict[str, Any]] = []
        while True:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=self.batch_interval)
                batch.append(item)
                if len(batch) >= self.batch_size:
                    await self._flush_batch(batch)
                    batch = []
            except asyncio.TimeoutError:
                if batch:
                    await self._flush_batch(batch)
                    batch = []
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Telemetry worker encountered unexpected error")

    async def _flush_batch(self, batch: List[Dict[str, Any]]) -> None:
        if not batch:
            return
        if not self.enabled:
            for item in batch:
                logger.debug("Telemetry (noop) %s: %s", item["kind"], item["payload"])
            return
        metrics: List[Dict[str, Any]] = []
        sessions: List[Dict[str, Any]] = []
        role_switches: List[Dict[str, Any]] = []
        for item in batch:
            if item["kind"] == "metric":
                metrics.append(item["payload"])
            elif item["kind"] == "session":
                sessions.append(item["payload"])
            elif item["kind"] == "role_switch":
                role_switches.append(item["payload"])
                if role_switches:
                    await client.post(
                        f"{self.supabase_url}/rest/v1/{self.role_switch_table}",
                        headers=headers,
                        content=json.dumps(role_switches),
                    )
        async with httpx.AsyncClient(timeout=10.0) as client:  # type: ignore[call-arg]
            headers = {
                "apikey": self.supabase_service_key,
                "Authorization": f"Bearer {self.supabase_service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            }
            try:
                if sessions:
                    await client.post(
                        f"{self.supabase_url}/rest/v1/{self.sessions_table}",
                        headers=headers,
                        content=json.dumps(sessions),
                    )
                if metrics:
                    await client.post(
                        f"{self.supabase_url}/rest/v1/{self.metrics_table}",
                        headers=headers,
                        content=json.dumps(metrics),
                    )
            except Exception:
                logger.exception("Telemetry push failed")

    async def _drain_queue(self) -> None:
        items: List[Dict[str, Any]] = []
        while not self.queue.empty():
            try:
                items.append(self.queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if items:
            await self._flush_batch(items)


_telemetry_client: Optional[TelemetryClient] = None


def get_telemetry_client() -> TelemetryClient:
    global _telemetry_client
    if _telemetry_client is None:
        _telemetry_client = TelemetryClient()
    return _telemetry_client

