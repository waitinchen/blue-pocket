"""FastAPI WebSocket endpoint for streaming audio to Whisper."""

import json
import logging
import os
import tempfile
from collections import deque
from pathlib import Path
from typing import Deque, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from openai import OpenAI

router = APIRouter()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY")
CHUNK_THRESHOLD = 4  # number of MediaRecorder chunks (~2-4 seconds)
ENERGY_WINDOW_SECONDS = 4
ENERGY_SAMPLE_RATE = 60  # expected client-side sampling per second
DEFAULT_MIME_TYPE = "audio/webm"

MIME_SUFFIX_MAP = {
    "audio/webm": ".webm",
    "audio/webm;codecs=opus": ".webm",
    "audio/ogg": ".ogg",
    "audio/ogg;codecs=opus": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mp4;codecs=opus": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
}

logger = logging.getLogger("voice_agent")

client: Optional[OpenAI] = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)


def _verify_service_key(websocket: WebSocket) -> bool:
    if not SERVICE_API_KEY:
        return True
    provided = (
        websocket.headers.get("Service-Api-Key")
        or websocket.headers.get("x-service-api-key")
        or websocket.query_params.get("service_api_key")
    )
    client_host = websocket.client.host if websocket.client else "unknown"
    if provided != SERVICE_API_KEY:
        logger.warning("whisper websocket api key invalid", extra={"client": client_host})
        return False
    logger.info("whisper websocket api key verified", extra={"client": client_host})
    return True


def _estimate_emotion(avg_energy: float) -> str:
    if avg_energy >= 65:
        return "happy"
    if avg_energy <= 35:
        return "soft"
    return "neutral"


def _summarize_energy(
    energy_values: Deque[float],
    peak_energy: float,
    forced_emotion: Optional[str] = None,
) -> Optional[dict]:
    if not energy_values:
        return None
    avg_energy = sum(energy_values) / len(energy_values)
    emotion = forced_emotion or _estimate_emotion(avg_energy)
    return {
        "avgEnergy": round(avg_energy, 2),
        "peakEnergy": round(peak_energy, 2),
        "emotionEstimate": emotion,
    }


async def _transcribe_chunks(chunks: List[bytes], file_suffix: str) -> str:
    """Persist chunks to a temp file and call Whisper transcription."""
    if not client:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
        for chunk in chunks:
            tmp_file.write(chunk)
        temp_path = Path(tmp_file.name)

    try:
        with temp_path.open("rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=audio_file,
            )
        return response.text or ""
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


async def transcribe_media_chunks(chunks: List[bytes], mime_type: str) -> str:
    """
    Helper shared by realtime pipelines to transcribe MediaRecorder chunks with Whisper.
    """
    if not chunks:
        return ""
    file_suffix = MIME_SUFFIX_MAP.get(mime_type, ".webm")
    return await _transcribe_chunks(chunks, file_suffix)


def summarize_energy_window(
    energy_values: Deque[float],
    peak_energy: float,
    forced_emotion: Optional[str] = None,
) -> Optional[dict]:
    """
    Summarize rolling energy metrics in a format suitable for frontend visualisation.
    """
    return _summarize_energy(energy_values, peak_energy, forced_emotion)


def estimate_emotion(avg_energy: float) -> str:
    """
    Expose default energy→emotion mapping for other modules.
    """
    return _estimate_emotion(avg_energy)


@router.websocket("/api/whisper")
async def whisper_websocket(websocket: WebSocket):
    if not _verify_service_key(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    mime_type = websocket.query_params.get("mime_type", DEFAULT_MIME_TYPE)
    file_suffix = MIME_SUFFIX_MAP.get(mime_type, ".webm")

    await websocket.accept()

    if not client:
        await websocket.send_json(
            {
                "type": "error",
                "message": "OPENAI_API_KEY 未設定，無法使用 Whisper 服務",
            }
        )
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    audio_chunks: List[bytes] = []
    energy_history: Deque[float] = deque(maxlen=ENERGY_WINDOW_SECONDS * ENERGY_SAMPLE_RATE)
    peak_energy: float = 0.0
    last_metrics: Optional[dict] = None

    try:
        await websocket.send_json({"type": "ready"})

        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"] is not None:
                audio_chunks.append(message["bytes"])

                if len(audio_chunks) >= CHUNK_THRESHOLD:
                    try:
                        text = await transcribe_media_chunks(audio_chunks, mime_type)
                        payload = {"type": "final", "text": text}
                        metrics = summarize_energy_window(energy_history, peak_energy)
                        if metrics:
                            payload["energyMetrics"] = metrics
                            last_metrics = metrics
                        await websocket.send_json(payload)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("whisper transcribe failed", exc_info=exc)
                        await websocket.send_json({"type": "error", "message": str(exc)})
                    finally:
                        audio_chunks.clear()

            elif "text" in message and message["text"] is not None:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                if data.get("type") == "energy":
                    avg = float(data.get("avg", 0.0))
                    peak = float(data.get("peak", avg))
                    emotion = data.get("emotionEstimate")

                    energy_history.append(avg)
                    peak_energy = max(peak, peak_energy * 0.92)

                    metrics = summarize_energy_window(energy_history, peak_energy, emotion)
                    if metrics:
                        last_metrics = metrics
                        # 回傳即時能量（可選）
                        await websocket.send_json({"type": "energy", "energyMetrics": metrics})

            elif message.get("type") == "websocket.disconnect":
                break

    except WebSocketDisconnect:
        pass
    finally:
        if audio_chunks:
            try:
                text = await transcribe_media_chunks(audio_chunks, mime_type)
                payload = {"type": "final", "text": text}
                metrics = last_metrics or summarize_energy_window(energy_history, peak_energy)
                if metrics:
                    payload["energyMetrics"] = metrics
                await websocket.send_json(payload)
            except Exception:
                pass
        audio_chunks.clear()

