"""
🚀 FastAPI 後端 API：黃蓉語音系統對外接口

提供 REST API 供外部系統調用，支援：
- POST /api/voice/huangrong - 產生語音並回傳 URL
- POST /api/voice/huangrong/stream - 直接返回音訊流
"""

import asyncio
import audioop
import base64
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
from typing import Deque, Dict, List, Optional

import jwt
import requests
from fastapi import Depends, FastAPI, HTTPException, Request, Header, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# 導入模組
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.llm_emotion_router import llm_emotion_route
from modules.speech_tag_mapper import extract_tags_from_text
from modules.voice_cache_engine import (
    ensure_cache_dir,
    generate_audio_key,
    get_cached_audio_path,
    is_cache_valid,
    clean_expired_cache,
)
from eleven_tts import generate_speech, API_KEY, VOICE_ID

from .whisper_api import (
    router as whisper_router,
    transcribe_media_chunks,
    summarize_energy_window,
    ENERGY_WINDOW_SECONDS,
    ENERGY_SAMPLE_RATE,
)
from modules.audio_decode import decode_to_wav16k
from modules.telemetry import get_telemetry_client
from modules.emotion_ai import EmotionAIWorker, EmotionSnapshot
from modules.role_registry import RoleRegistry, RoleChannelConfig

try:
    from faster_whisper import WhisperModel  # type: ignore
    _WHISPER_AVAILABLE = True
except Exception:
    _WHISPER_AVAILABLE = False
    WhisperModel = None  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_agent")

SENTRY_DSN = os.getenv("SENTRY_DSN")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0"))

if SENTRY_DSN:
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE)
        logger.info("Sentry initialized")
    except ImportError:
        logger.warning("sentry-sdk 未安裝，無法初始化 Sentry")


app = FastAPI(
    title="黃蓉語音系統 API",
    description="ElevenLabs v3 語音合成 API，支援自動語氣標籤",
    version="2.0.0"
)

app.include_router(whisper_router)
telemetry_client = get_telemetry_client()
emotion_ai_worker = EmotionAIWorker() if ENABLE_EMOTION_AI_P1 else None
role_registry = RoleRegistry()


@app.on_event("startup")
async def startup_event() -> None:
    await telemetry_client.start()
    logger.info("Gateway roles available: %s", list(role_registry.list_roles().keys()))


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await telemetry_client.stop()

# Health and version endpoints
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {"version": "2.0.0"}

# CORS 設定（允許前端調用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境請設定特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 設定音訊儲存目錄
AUDIO_DIR = Path("public/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY")
RATE_LIMIT_PER_MIN = int(os.getenv("SERVICE_RATE_LIMIT_PER_MIN", "60"))
ELEVEN_MAX_RETRIES = int(os.getenv("ELEVEN_MAX_RETRIES", "3"))
ELEVEN_RETRY_BACKOFF = float(os.getenv("ELEVEN_RETRY_BACKOFF", "1.5"))
CHATKIT_CLIENT_SECRET_SEED = os.getenv("CHATKIT_CLIENT_SECRET_SEED")
CHATKIT_SESSION_TTL_MIN = int(os.getenv("CHATKIT_SESSION_TTL_MIN", "30"))
CHATKIT_JWT_ALGORITHM = os.getenv("CHATKIT_JWT_ALGORITHM", "HS256")
THROTTLE_MS = int(os.getenv("STT_THROTTLE_MS", "700"))
SILENCE_MS = int(os.getenv("STT_SILENCE_MS", "1500"))
ENERGY_MS = int(os.getenv("STT_ENERGY_MS", "120"))
REALTIME_PARTIAL_INTERVAL_MS = int(os.getenv("REALTIME_PARTIAL_INTERVAL_MS", str(THROTTLE_MS)))
REALTIME_FINAL_SILENCE_MS = int(os.getenv("REALTIME_FINAL_SILENCE_MS", str(SILENCE_MS)))
REALTIME_CHUNK_THRESHOLD = int(os.getenv("REALTIME_CHUNK_THRESHOLD", "3"))
GATEWAY_JWT_SECRET = os.getenv("GATEWAY_JWT_SECRET", SERVICE_API_KEY or "")
GATEWAY_JWT_ALGORITHM = os.getenv("GATEWAY_JWT_ALGORITHM", CHATKIT_JWT_ALGORITHM or "HS256")
GATEWAY_JWT_AUDIENCE = os.getenv("GATEWAY_JWT_AUDIENCE")
GATEWAY_JWT_ISSUER = os.getenv("GATEWAY_JWT_ISSUER")
ENABLE_EMOTION_AI_P1 = os.getenv("ENABLE_EMOTION_AI_P1", "false").lower() in {"1", "true", "yes"}

async def _handle_voice_stream(ws: WebSocket):
    token = _extract_gateway_token(ws)
    authorized = False
    if token and _verify_gateway_jwt(token):
        authorized = True
    elif _verify_ws_service_key(ws):
        authorized = True
    if not authorized:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if not await _enforce_gateway_rate_limit(ws):
        await ws.close(code=status.WS_1013_TRY_AGAIN_LATER)
        return
    await ws.accept()
    session = LingyaGatewayMultiRole(
        ws,
        default_voice_id=VOICE_ID,
        registry=role_registry,
        emotion_worker=emotion_ai_worker,
    )
    await session.notify_ready()
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if "text" in msg and msg["text"] is not None:
                await session.handle_text_message(msg["text"])
            elif "bytes" in msg and msg["bytes"] is not None:
                await session.handle_binary_chunk(msg["bytes"])
            await session.tick()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        await session.handle_exception(exc)
    finally:
        await session.close()


@app.websocket("/api/voice/stream")
async def voice_stream(ws: WebSocket):
    await _handle_voice_stream(ws)


@app.websocket("/api/realtime/ws")
async def realtime_ws(ws: WebSocket):
    await _handle_voice_stream(ws)


# ElevenLabs streaming TTS over WebSocket
@app.websocket("/api/voice/stream-ws")
async def tts_stream_ws(ws: WebSocket):
    await ws.accept()
    if not API_KEY:
        await ws.send_json({"type": "error", "message": "ELEVEN_API_KEY not configured"})
        await ws.close()
        return
    import base64
    import json as _json
    import requests

    session = None
    try:
        while True:
            msg = await ws.receive_text()
            try:
                payload = _json.loads(msg)
            except Exception:
                await ws.send_json({"type": "error", "message": "invalid_json"})
                continue

            mtype = payload.get("type")
            if mtype == "ping":
                await ws.send_text("pong")
                continue
            if mtype == "stop":
                # no persistent stream kept; client can just stop consuming
                await ws.send_json({"type": "tts_done"})
                continue
            if mtype == "speech":
                text = payload.get("text", "").strip()
                voice = payload.get("voice_id") or VOICE_ID
                if not text:
                    await ws.send_json({"type": "error", "message": "empty_text"})
                    continue
                if not voice:
                    await ws.send_json({"type": "error", "message": "no_voice_id"})
                    continue

                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/stream"
                headers = {"xi-api-key": API_KEY, "Content-Type": "application/json"}
                body = {
                    "model_id": "eleven_turbo_v2_5",
                    "text": text,
                    "voice_settings": {
                        "stability": 0.4,
                        "similarity_boost": 0.8,
                        "style": 0.9,
                        "use_speaker_boost": True,
                    },
                }
                try:
                    # TTS chunk config
                    TTS_CHUNK_BYTES = int(os.getenv("TTS_CHUNK_BYTES", "24576"))  # 24KB
                    AGGREGATE = int(os.getenv("TTS_AGGREGATE", "2"))  # aggregate N chunks per message
                    with requests.post(url, headers=headers, json=body, stream=True, timeout=30) as r:
                        r.raise_for_status()
                        agg = bytearray()
                        count = 0
                        for chunk in r.iter_content(chunk_size=TTS_CHUNK_BYTES):
                            if not chunk:
                                continue
                            agg.extend(chunk)
                            count += 1
                            if count >= AGGREGATE:
                                b64 = base64.b64encode(bytes(agg)).decode("ascii")
                                await ws.send_json({"type": "tts_chunk", "mime": "audio/mpeg", "data": b64})
                                agg.clear(); count = 0
                        if agg:
                            b64 = base64.b64encode(bytes(agg)).decode("ascii")
                            await ws.send_json({"type": "tts_chunk", "mime": "audio/mpeg", "data": b64})
                        await ws.send_json({"type": "tts_done"})
                except Exception as e:  # noqa: BLE001
                    await ws.send_json({"type": "error", "message": f"tts_failed: {str(e)}"})
            else:
                await ws.send_json({"type": "error", "message": "unknown_type"})
    except WebSocketDisconnect:
        return


# Agent route: STT text -> LLM reply -> TTS URL
class AgentRequest(BaseModel):
    text: str
    provider: Optional[str] = "openai"
    voice_id: Optional[str] = None


class AgentResponse(BaseModel):
    reply_text: str
    audio_url: Optional[str] = None


@app.post("/api/agent/reply", response_model=AgentResponse, dependencies=[Depends(verify_api_key), Depends(enforce_rate_limit)])
async def agent_reply(body: AgentRequest, http_request: Request):
    try:
        # 1) LLM 產生回覆（沿用現有情感路由，可改 provider）
        reply_text = llm_emotion_route(body.text, provider=body.provider, fallback_to_rule=True)

        # 2) 生成語音（沿用現有 generate_speech 流程與快取機制）
        vid = body.voice_id or VOICE_ID
        if not vid:
            raise HTTPException(status_code=500, detail="Missing default VOICE_ID")

        # 直接用現有 API 的快取機制：寫入為一次性檔，回傳 URL
        # 這裡重用 generate_speech 的包裝：為保持最小改動，直接呼叫並寫入臨時檔案
        # 使用與 /api/voice/huangrong 相同的設定
        from modules.speech_tag_mapper import extract_tags_from_text
        from modules.voice_cache_engine import (
            generate_audio_key,
            get_cached_audio_path,
            is_cache_valid,
            clean_expired_cache,
        )

        tags = extract_tags_from_text(reply_text)
        cache_key = generate_audio_key(reply_text, vid, tags)
        cache_path = get_cached_audio_path(cache_key)
        if not is_cache_valid(cache_path):
            payload = {
                "model_id": "eleven_turbo_v2_5",
                "text": reply_text,
                "voice_settings": {
                    "stability": 0.4,
                    "similarity_boost": 0.8,
                    "style": 0.9,
                    "use_speaker_boost": True,
                },
            }
            resp = call_elevenlabs_generate(payload, vid)
            with open(cache_path, "wb") as f:
                f.write(resp.content)
            clean_expired_cache()

        audio_url = f"{BASE_URL}/audio/{cache_path.name}"
        return AgentResponse(reply_text=reply_text, audio_url=audio_url)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("agent_reply failed")
        raise HTTPException(status_code=500, detail=str(e))

_rate_state: Dict[str, tuple[int, int]] = {}
_rate_lock = asyncio.Lock()
_gateway_rate_state: Dict[str, tuple[int, int]] = {}
_gateway_rate_lock = asyncio.Lock()

ensure_cache_dir()


class VoiceRequest(BaseModel):
    """語音請求模型"""
    text: str
    provider: Optional[str] = "openai"  # LLM provider: "openai" 或 "anthropic"
    emotion_auto: Optional[bool] = True  # 是否自動判斷語氣
    voice_id: Optional[str] = None  # 可選：指定不同的 voice_id


class VoiceResponse(BaseModel):
    """語音回應模型"""
    status: str
    audio_url: Optional[str] = None
    text: Optional[str] = None
    tagged_text: Optional[str] = None
    voice_tags: Optional[list[str]] = None
    cache_hit: Optional[bool] = None
    message: Optional[str] = None


class ChatKitSessionRequest(BaseModel):
    """ChatKit session 請求模型"""
    service_key: Optional[str] = None


async def verify_api_key(request: Request, service_api_key: Optional[str] = Header(None, alias="Service-Api-Key")) -> None:
    """Verify client provided service API key."""
    if not SERVICE_API_KEY:
        return

    provided = (
        service_api_key
        or request.headers.get("x-service-api-key")
        or request.query_params.get("service_api_key")
    )

    client_host = request.client.host if request.client else "unknown"

    if provided != SERVICE_API_KEY:
        logger.warning(
            "service api key invalid",
            extra={"path": request.url.path, "client": client_host},
        )
        raise HTTPException(status_code=401, detail="Invalid Service API Key")

    logger.info(
        "service api key verified",
        extra={"path": request.url.path, "client": client_host},
    )


def _verify_ws_service_key(websocket: WebSocket) -> bool:
    """Inline verifier for WebSocket connections."""
    if not SERVICE_API_KEY:
        return True
    provided = (
        websocket.headers.get("Service-Api-Key")
        or websocket.headers.get("x-service-api-key")
        or websocket.query_params.get("service_api_key")
    )
    client_host = websocket.client.host if websocket.client else "unknown"
    if provided != SERVICE_API_KEY:
        logger.warning("service api key invalid", extra={"path": websocket.url.path, "client": client_host})
        return False
    logger.info("service api key verified", extra={"path": websocket.url.path, "client": client_host})
    return True


def _extract_gateway_token(websocket: WebSocket) -> Optional[str]:
    auth = websocket.headers.get("Authorization") or websocket.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    token = websocket.query_params.get("token")
    if token:
        return token.strip()
    return None


def _verify_gateway_jwt(token: str) -> bool:
    if not token:
        return False
    if not GATEWAY_JWT_SECRET:
        return False
    options = {"verify_aud": bool(GATEWAY_JWT_AUDIENCE), "verify_iss": bool(GATEWAY_JWT_ISSUER)}
    try:
        jwt.decode(
            token,
            GATEWAY_JWT_SECRET,
            algorithms=[GATEWAY_JWT_ALGORITHM],
            audience=GATEWAY_JWT_AUDIENCE if GATEWAY_JWT_AUDIENCE else None,
            issuer=GATEWAY_JWT_ISSUER if GATEWAY_JWT_ISSUER else None,
            options=options,
        )
        return True
    except jwt.PyJWTError as exc:  # type: ignore[attr-defined]
        logger.warning("gateway jwt invalid", exc_info=exc)
        return False


async def _enforce_gateway_rate_limit(websocket: WebSocket) -> bool:
    if RATE_LIMIT_PER_MIN <= 0:
        return True
    identifier = (
        websocket.headers.get("Service-Api-Key")
        or websocket.headers.get("x-service-api-key")
        or _extract_gateway_token(websocket)
        or (websocket.client.host if websocket.client else "anonymous")
    )
    current_bucket = int(time.time() // 60)
    async with _gateway_rate_lock:
        count, bucket = _gateway_rate_state.get(identifier, (0, current_bucket))
        if bucket != current_bucket:
            count = 0
            bucket = current_bucket
        if count >= RATE_LIMIT_PER_MIN:
            logger.warning("Gateway rate limit exceeded", extra={"client": identifier})
            return False
        _gateway_rate_state[identifier] = (count + 1, bucket)
    return True


@app.post("/api/chatkit/session")
async def create_chatkit_session(payload: ChatKitSessionRequest):
    """
    簽發 ChatKit 前端使用的 client secret。

    前端需在請求 body 內帶入 service_key（與 SERVICE_API_KEY 相同），
    以防止未授權的 client 取得 token。
    """
    if SERVICE_API_KEY and payload.service_key != SERVICE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid service key")

    secret_seed = CHATKIT_CLIENT_SECRET_SEED or SERVICE_API_KEY
    if not secret_seed:
        raise HTTPException(status_code=500, detail="CHATKIT secret seed 未設定")

    now = datetime.utcnow()
    token = jwt.encode(
        {
            "scope": "chatkit-client",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=CHATKIT_SESSION_TTL_MIN)).timestamp()),
        },
        secret_seed,
        algorithm=CHATKIT_JWT_ALGORITHM,
    )
    return {"client_secret": token}


async def enforce_rate_limit(request: Request) -> None:
    if RATE_LIMIT_PER_MIN <= 0:
        return

    identifier = request.headers.get("x-service-api-key") or (request.client.host if request.client else "anonymous")
    current_bucket = int(time.time() // 60)

    async with _rate_lock:
        count, bucket = _rate_state.get(identifier, (0, current_bucket))
        if bucket != current_bucket:
            count = 0
            bucket = current_bucket

        if count >= RATE_LIMIT_PER_MIN:
            logger.warning("Rate limit exceeded", extra={"client": identifier, "path": request.url.path})
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        _rate_state[identifier] = (count + 1, bucket)


def call_elevenlabs_generate(payload: dict, voice_id: str):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "xi-api-key": API_KEY,
        "Content-Type": "application/json"
    }
    retry_wait = ELEVEN_RETRY_BACKOFF
    last_error: Optional[Exception] = None

    for attempt in range(1, ELEVEN_MAX_RETRIES + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                return response
            last_error = HTTPException(status_code=response.status_code, detail=f"ElevenLabs API 錯誤：{response.text}")
            logger.warning("ElevenLabs call failed", extra={"attempt": attempt, "status": response.status_code})
        except requests.RequestException as exc:  # noqa: BLE001
            last_error = exc
            logger.error("ElevenLabs request exception", exc_info=exc, extra={"attempt": attempt})

        if attempt < ELEVEN_MAX_RETRIES:
            time.sleep(retry_wait)
            retry_wait *= 2

    if isinstance(last_error, HTTPException):
        raise last_error
    if isinstance(last_error, Exception):
        raise HTTPException(status_code=502, detail=str(last_error))
    raise HTTPException(status_code=502, detail="ElevenLabs API 錯誤")


def call_elevenlabs_stream(payload: dict, voice_id: str):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "xi-api-key": API_KEY,
        "Content-Type": "application/json"
    }
    retry_wait = ELEVEN_RETRY_BACKOFF
    last_exc: Optional[Exception] = None

    for attempt in range(1, ELEVEN_MAX_RETRIES + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30, stream=True)
            if response.status_code == 200:
                return response
            logger.warning("ElevenLabs stream failed", extra={"attempt": attempt, "status": response.status_code})
        except requests.RequestException as exc:  # noqa: BLE001
            last_exc = exc
            logger.error("ElevenLabs stream exception", exc_info=exc, extra={"attempt": attempt})

        if attempt < ELEVEN_MAX_RETRIES:
            time.sleep(retry_wait)
            retry_wait *= 2

    if last_exc:
        raise last_exc
    raise HTTPException(status_code=502, detail="ElevenLabs stream 呼叫失敗")


def _compute_energy_levels(wav_bytes: bytes) -> tuple[float, float]:
    """Return (avg_energy, peak_energy) scaled 0-100 from 16-bit PCM wav bytes."""
    if len(wav_bytes) <= 44:
        return 0.0, 0.0
    pcm = wav_bytes[44:]
    if not pcm:
        return 0.0, 0.0
    try:
        rms = audioop.rms(pcm, 2)
        peak = audioop.max(pcm, 2)
    except audioop.error:
        return 0.0, 0.0
    avg = min(100.0, (rms / 32768.0) * 100.0)
    peak_level = min(100.0, (peak / 32768.0) * 100.0 if peak else 0.0)
    return avg, peak_level


class LingyaGatewayMultiRole:
    """Gateway-managed session supporting multi-role orchestration."""

    def __init__(
        self,
        websocket: WebSocket,
        default_voice_id: Optional[str],
        registry: RoleRegistry,
        emotion_worker: Optional[EmotionAIWorker],
    ):
        self.session_id = str(uuid.uuid4())
        self.ws = websocket
        self.voice_id = default_voice_id or VOICE_ID
        self.provider = "openai"
        self.mime_type = "audio/webm"
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.closed_at: Optional[float] = None
        self.phase = "idle"

        self.role_id: Optional[str] = None
        self.role_config: Optional[RoleChannelConfig] = None
        self.registry = registry

        self.audio_chunks: List[bytes] = []
        self.energy_history: Deque[float] = deque(maxlen=ENERGY_WINDOW_SECONDS * ENERGY_SAMPLE_RATE)
        self.peak_energy: float = 0.0
        self.last_energy_ms = 0
        self.last_chunk_ms = int(time.time() * 1000)
        self.last_partial_ms = 0
        self.partial_task: Optional[asyncio.Task] = None
        self.partial_lock = asyncio.Lock()
        self.partial_transcript: List[str] = []
        self.remote_cache_text: str = ""
        self.using_local_whisper = _WHISPER_AVAILABLE
        self.whisper_model: Optional[WhisperModel] = None
        self.finalized = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None

        self.metrics_samples: List[dict] = []
        self.stt_latency_samples: List[float] = []
        self.tts_first_chunk_latency_ms: Optional[int] = None
        self.error_count = 0
        self.last_metrics_payload: Optional[dict] = None
        self.emotion_worker = emotion_worker
        self.last_emotion_snapshot: Optional[EmotionSnapshot] = None

    async def notify_ready(self) -> None:
        self.loop = asyncio.get_running_loop()
        await self.ws.send_json(
            {
                "type": "gateway.ready",
                "timestamp": int(time.time() * 1000),
                "session_id": self.session_id,
            }
        )

    async def handle_text_message(self, data: str) -> None:
        if not data:
            return
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("gateway invalid json message", extra={"session": self.session_id})
            return
        message_type = payload.get("type")
        if message_type in ("ping", "voice.ping"):
            await self.ws.send_json({"type": "gateway.pong", "timestamp": int(time.time() * 1000)})
            return
        if message_type == "voice.start":
            await self._handle_voice_start(payload)
        elif message_type == "voice.data":
            await self._handle_voice_data(payload)
        elif message_type == "voice.end":
            await self.finalize(reason="client_end")
        elif message_type == "voice.switch":
            await self._handle_role_switch(payload)
        elif message_type == "voice.roles":
            await self._emit_role_catalog()
        elif message_type == "config":
            mime = payload.get("mime_type")
            if isinstance(mime, str) and mime:
                self.mime_type = mime
        else:
            logger.debug("gateway unknown message type %s", message_type)

    async def handle_binary_chunk(self, chunk: bytes) -> None:
        if not chunk:
            return
        if not await self._ensure_active_or_error():
            return
        await self._process_audio_chunk(chunk, timestamp_ms=int(time.time() * 1000))

    async def tick(self) -> None:
        if self.finalized or self.phase in {"idle", "closed"}:
            return
        now_ms = int(time.time() * 1000)
        if self.audio_chunks and now_ms - self.last_chunk_ms >= REALTIME_FINAL_SILENCE_MS:
            await self.finalize(reason="silence_timeout")

    async def finalize(self, reason: str, error: Optional[str] = None) -> None:
        if self.finalized:
            return
        self.finalized = True
        previous_phase = self.phase
        self.phase = "closed"
        if self.partial_task:
            try:
                await self.partial_task
            except Exception:
                pass
            finally:
                self.partial_task = None

        if previous_phase in {"listen", "respond"}:
            if self.using_local_whisper:
                final_text = " ".join(self.partial_transcript).strip()
                if final_text:
                    await self._emit_metrics({"transcript": final_text, "is_final": True})
                    await self._handle_final_reply(final_text)
            else:
                await self._transcribe_remote(final=True)

        self.closed_at = time.time()
        if self.role_id:
            self.registry.release_role(self.role_id, self.session_id)
        await self._emit_session_closed(reason=reason, error=error)
        self._reset_buffers()

    async def close(self) -> None:
        if not self.finalized:
            await self.finalize(reason="disconnect")

    async def handle_exception(self, exc: Exception) -> None:
        self.error_count += 1
        self.phase = "error"
        message = str(exc)
        logger.exception("gateway session error", extra={"session": self.session_id})
        try:
            await self.ws.send_json(
                {"type": "error", "session_id": self.session_id, "message": message}
            )
        except Exception:
            pass
        await self.finalize(reason="error", error=message)

    async def _handle_voice_start(self, payload: dict) -> None:
        if self.phase in {"listen", "respond"}:
            await self.ws.send_json(
                {"type": "voice.ack", "session_id": self.session_id, "voice_id": self.voice_id, "role_id": self.role_id}
            )
            return
        self.started_at = time.time()
        requested_role = payload.get("role_id")
        try:
            role_config = self.registry.acquire_role(requested_role, self.session_id)
            self.role_config = role_config
            self.role_id = role_config.role_id
            self.voice_id = role_config.voice_id or self.voice_id
        except Exception as exc:
            self.phase = "error"
            await self.ws.send_json(
                {
                    "type": "voice.role_status",
                    "session_id": self.session_id,
                    "role_id": requested_role,
                    "status": "error",
                    "message": str(exc),
                }
            )
            raise

        if isinstance(payload.get("provider"), str):
            self.provider = payload["provider"]
        if isinstance(payload.get("mime_type"), str):
            self.mime_type = payload["mime_type"]

        self.phase = "listen"
        await self.ws.send_json(
            {
                "type": "voice.ack",
                "session_id": self.session_id,
                "voice_id": self.voice_id,
                "role_id": self.role_id,
                "phase": self.phase,
                "timestamp": int(self.started_at * 1000),
            }
        )
        await self._emit_role_status(status="active", message="role_initialized", latency_ms=0)

    async def _handle_voice_data(self, payload: dict) -> None:
        if not await self._ensure_active_or_error():
            return
        chunk_b64 = payload.get("chunk")
        if not isinstance(chunk_b64, str):
            await self.ws.send_json(
                {"type": "error", "session_id": self.session_id, "message": "invalid_chunk"}
            )
            return
        try:
            chunk = base64.b64decode(chunk_b64)
        except Exception:
            await self.ws.send_json(
                {"type": "error", "session_id": self.session_id, "message": "chunk_decode_failed"}
            )
            return
        timestamp_ms = int(payload.get("timestamp", time.time() * 1000))
        await self._process_audio_chunk(chunk, timestamp_ms=timestamp_ms)

    async def _process_audio_chunk(self, chunk: bytes, timestamp_ms: int) -> None:
        now_ms = timestamp_ms or int(time.time() * 1000)
        self.audio_chunks.append(chunk)
        self.last_chunk_ms = now_ms
        if self.phase == "idle":
            self.phase = "listen"

        metrics_payload: Dict[str, Any] = {"timestamp": now_ms, "role_id": self.role_id}
        avg_energy_value: Optional[float] = None
        peak_energy_value: Optional[float] = None

        try:
            wav = decode_to_wav16k(chunk)
            avg, peak = _compute_energy_levels(wav)
            if avg:
                self.energy_history.append(avg)
                self.peak_energy = max(peak, self.peak_energy * 0.92)
                if now_ms - self.last_energy_ms >= ENERGY_MS:
                    metrics = summarize_energy_window(self.energy_history, self.peak_energy)
                    if metrics:
                        avg_energy_value = metrics["avgEnergy"]
                        peak_energy_value = metrics["peakEnergy"]
                        metrics_payload.update(
                            {
                                "avg_energy": avg_energy_value,
                                "peak_energy": peak_energy_value,
                                "emotion_estimate": metrics["emotionEstimate"],
                            }
                        )
                        if self.role_id:
                            self.registry.update_emotion_state(self.role_id, metrics["emotionEstimate"])

                        if self.emotion_worker:
                            snapshot = self.emotion_worker.analyze(
                                wav,
                                avg_energy_value,
                                peak_energy_value,
                            )
                            self.last_emotion_snapshot = snapshot
                            metrics_payload.update(self.emotion_worker.to_payload(snapshot))
                            if snapshot.emotion_estimate:
                                metrics_payload["emotion_estimate"] = snapshot.emotion_estimate

                        await self._emit_metrics(metrics_payload.copy())
                    self.last_energy_ms = now_ms
        except Exception as exc:  # noqa: BLE001
            logger.debug("energy feedback failed", exc_info=exc)

        if self.using_local_whisper:
            await self._transcribe_local_chunk(chunk, is_final=False)
        else:
            if (
                not self.partial_task
                and now_ms - self.last_partial_ms >= REALTIME_PARTIAL_INTERVAL_MS
                and len(self.audio_chunks) >= REALTIME_CHUNK_THRESHOLD
            ):
                self.partial_task = asyncio.create_task(self._transcribe_remote(final=False))
                self.last_partial_ms = now_ms

    async def _transcribe_local_chunk(self, chunk: bytes, is_final: bool) -> None:
        try:
            if self.whisper_model is None:
                model_size = os.getenv("REALTIME_WHISPER_MODEL", "tiny")
                whisper_device = os.getenv("REALTIME_WHISPER_DEVICE", "cpu")
                compute_type = os.getenv("REALTIME_WHISPER_COMPUTE", "int8")
                self.whisper_model = WhisperModel(model_size, device=whisper_device, compute_type=compute_type)
            start_ts = time.time()
            wav = decode_to_wav16k(chunk)
            segments, _ = await asyncio.to_thread(
                self.whisper_model.transcribe,
                wav,
                vad_filter=True,
            )
            latency_ms = int((time.time() - start_ts) * 1000)
            self.stt_latency_samples.append(latency_ms)
            text_parts = [s.text.strip() for s in segments if getattr(s, "text", "").strip()]
            if text_parts:
                self.partial_transcript.extend(text_parts)
                combined = " ".join(self.partial_transcript).strip()
                if combined:
                    await self._emit_metrics(
                        {"transcript": combined, "is_final": is_final, "latency_ms": latency_ms, "role_id": self.role_id}
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("local whisper transcribe failed", exc_info=exc)
            await self.ws.send_json({"type": "error", "session_id": self.session_id, "message": f"stt_failed: {exc}"})
            self.using_local_whisper = False

    async def _transcribe_remote(self, final: bool) -> None:
        async with self.partial_lock:
            try:
                start_ts = time.time()
                text = await transcribe_media_chunks(list(self.audio_chunks), self.mime_type)
                latency_ms = int((time.time() - start_ts) * 1000)
                self.stt_latency_samples.append(latency_ms)
            except Exception as exc:  # noqa: BLE001
                logger.warning("remote whisper transcribe failed", exc_info=exc)
                await self.ws.send_json(
                    {"type": "error", "session_id": self.session_id, "message": f"stt_failed: {exc}"}
                )
                return

            text = (text or "").strip()
            if not text:
                return

            if not final and text == self.remote_cache_text:
                return

            self.remote_cache_text = text
            await self._emit_metrics({"transcript": text, "is_final": final, "latency_ms": latency_ms, "role_id": self.role_id})

            if final:
                await self._handle_final_reply(text)

    async def _handle_final_reply(self, user_text: str) -> None:
        text = user_text.strip()
        if not text:
            return
        self.phase = "respond"
        loop = asyncio.get_running_loop()
        try:
            reply_text = await loop.run_in_executor(
                None,
                llm_emotion_route,
                text,
                self.provider,
                None,
                True,
            )
        except Exception as exc:  # noqa: BLE001
            self.phase = "error"
            logger.exception("llm_emotion_route failed")
            await self.ws.send_json({"type": "error", "session_id": self.session_id, "message": f"llm_failed: {exc}"})
            return

        reply_text = reply_text.strip()
        tags = extract_tags_from_text(reply_text)
        await self.ws.send_json(
            {
                "type": "assistant.reply",
                "session_id": self.session_id,
                "text": reply_text,
                "tags": tags,
                "role_id": self.role_id,
            }
        )
        await self._stream_tts(reply_text)
        self.phase = "listen"

    async def _stream_tts(self, reply_text: str) -> None:
        voice_id = self.voice_id or VOICE_ID
        if not voice_id:
            await self.ws.send_json({"type": "error", "session_id": self.session_id, "message": "no_voice_id"})
            return

        payload = {
            "model_id": "eleven_turbo_v2_5",
            "text": reply_text,
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.8,
                "style": 0.9,
                "use_speaker_boost": True,
            },
        }

        queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()

        def worker():
            try:
                response = call_elevenlabs_stream(payload, voice_id)
                agg = bytearray()
                chunk_limit = int(os.getenv("TTS_CHUNK_BYTES", "24576"))
                aggregate_every = int(os.getenv("TTS_AGGREGATE", "2"))
                count = 0
                sequence = 0
                start_ts = time.time()
                first_chunk_emitted = False
                for chunk in response.iter_content(chunk_size=chunk_limit):
                    if not chunk:
                        continue
                    agg.extend(chunk)
                    count += 1
                    if count >= aggregate_every:
                        event = self._encode_tts_chunk(bytes(agg), sequence=sequence)
                        agg.clear()
                        count = 0
                        if event:
                            if not first_chunk_emitted:
                                first_chunk_emitted = True
                                queue.put_nowait({"__first_chunk_latency__": int((time.time() - start_ts) * 1000)})
                            queue.put_nowait(event)
                            sequence += 1
                if agg:
                    event = self._encode_tts_chunk(bytes(agg), sequence=sequence)
                    if event:
                        if sequence == 0:
                            queue.put_nowait({"__first_chunk_latency__": int((time.time() - start_ts) * 1000)})
                        queue.put_nowait(event)
                queue.put_nowait({"type": "tts.stream.completed", "session_id": self.session_id, "role_id": self.role_id})
            except HTTPException as exc:
                queue.put_nowait({"type": "error", "session_id": self.session_id, "message": str(exc.detail)})
            except Exception as exc:  # noqa: BLE001
                queue.put_nowait({"type": "error", "session_id": self.session_id, "message": f"tts_failed: {exc}"})
            finally:
                queue.put_nowait(None)

        threading.Thread(target=worker, daemon=True).start()

        while True:
            event = await queue.get()
            if event is None:
                break
            if "__first_chunk_latency__" in event:
                self.tts_first_chunk_latency_ms = event["__first_chunk_latency__"]
                continue
            await self.ws.send_json(event)

    def _encode_tts_chunk(self, data: bytes, sequence: int) -> Optional[dict]:
        if not data:
            return None
        b64 = base64.b64encode(data).decode("ascii")
        return {
            "type": "tts.stream",
            "session_id": self.session_id,
            "mime": "audio/mpeg",
            "chunk": b64,
            "sequence": sequence,
            "timestamp": int(time.time() * 1000),
            "role_id": self.role_id,
        }

    async def _emit_metrics(self, payload: dict) -> None:
        base_payload = {
            "type": "metrics",
            "session_id": self.session_id,
            "timestamp": int(time.time() * 1000),
            "role_id": self.role_id,
        }
        base_payload.update(payload)
        try:
            await self.ws.send_json(base_payload)
        except Exception:
            pass
        metric_record = {k: v for k, v in base_payload.items() if k not in {"type"}}
        self.metrics_samples.append(metric_record)
        self.last_metrics_payload = metric_record
        await telemetry_client.record_metric(metric_record)

    async def _handle_role_switch(self, payload: dict) -> None:
        if not await self._ensure_active_or_error():
            return
        requested_role = payload.get("role_id")
        if not isinstance(requested_role, str) or not requested_role:
            await self._emit_role_status(status="error", message="invalid_role_id", latency_ms=0)
            return
        if requested_role == self.role_id:
            await self._emit_role_status(status="active", message="role_unchanged", latency_ms=0)
            return
        start = time.time()
        prev_role = self.role_id
        self.phase = "pause"
        try:
            await self._emit_role_status(
                status="switching",
                message="role_switch_initiated",
                latency_ms=0,
                previous_role=prev_role,
                role_id=requested_role,
            )
            if not self.registry.can_switch(requested_role, self.session_id):
                raise RuntimeError("role_capacity_exceeded")
            config = self.registry.switch_role(prev_role or self.registry.default_role(), requested_role, self.session_id)
            self.role_config = config
            self.role_id = config.role_id
            self.voice_id = config.voice_id or self.voice_id
            latency_ms = int((time.time() - start) * 1000)
            await self._emit_role_status(
                status="active",
                message="role_switch_success",
                latency_ms=latency_ms,
                previous_role=prev_role,
            )
            await telemetry_client.record_role_switch(
                {
                    "session_id": self.session_id,
                    "from_role": prev_role,
                    "to_role": self.role_id,
                    "latency_ms": latency_ms,
                    "timestamp": int(time.time() * 1000),
                    "success": True,
                }
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.time() - start) * 1000)
            await self._emit_role_status(
                status="error",
                message=str(exc),
                latency_ms=latency_ms,
                role_id=requested_role,
            )
            await telemetry_client.record_role_switch(
                {
                    "session_id": self.session_id,
                    "from_role": prev_role,
                    "to_role": requested_role,
                    "latency_ms": latency_ms,
                    "timestamp": int(time.time() * 1000),
                    "success": False,
                    "error": str(exc),
                }
            )
        finally:
            if self.phase == "pause":
                self.phase = "listen"

    async def _emit_role_catalog(self) -> None:
        try:
            await self.ws.send_json({"type": "voice.roles", "roles": role_registry.list_roles()})
        except Exception:
            pass

    async def _emit_role_status(
        self,
        status: str,
        message: str,
        latency_ms: int,
        role_id: Optional[str] = None,
        previous_role: Optional[str] = None,
    ) -> None:
        payload = {
            "type": "voice.role_status",
            "session_id": self.session_id,
            "role_id": role_id or self.role_id,
            "status": status,
            "message": message,
            "latency_ms": latency_ms,
            "phase": self.phase,
            "timestamp": int(time.time() * 1000),
        }
        if previous_role:
            payload["previous_role"] = previous_role
        try:
            await self.ws.send_json(payload)
        except Exception:
            pass

    async def _emit_session_closed(self, reason: str, error: Optional[str]) -> None:
        duration_ms = None
        if self.started_at:
            duration_ms = int(((self.closed_at or time.time()) - self.started_at) * 1000)
        summary = {
            "type": "session.closed",
            "session_id": self.session_id,
            "reason": reason,
            "duration_ms": duration_ms,
            "voice_id": self.voice_id,
            "provider": self.provider,
            "role_id": self.role_id,
            "metrics": {
                "stt_latency_ms": self._reduce_samples(self.stt_latency_samples),
                "tts_first_chunk_ms": self.tts_first_chunk_latency_ms,
                "avg_energy": self._last_metric_field("avg_energy"),
                "peak_energy": self._last_metric_field("peak_energy"),
                "emotion_estimate": self._last_metric_field("emotion_estimate"),
                "pitch_hz": self._last_metric_field("pitch_hz"),
                "emotion_confidence": self._last_metric_field("emotion_confidence"),
            },
            "errors": self.error_count,
        }
        if error:
            summary["error_message"] = error
        try:
            await self.ws.send_json(summary)
        except Exception:
            pass
        logger.info("gateway.session.summary", extra={"summary": summary})
        await telemetry_client.record_session(summary)

    def _last_metric_field(self, field: str) -> Optional[float]:
        if not self.last_metrics_payload:
            return None
        return self.last_metrics_payload.get(field)

    @staticmethod
    def _reduce_samples(samples: List[float]) -> Optional[dict]:
        if not samples:
            return None
        samples_sorted = sorted(samples)
        n = len(samples_sorted)
        p50 = samples_sorted[n // 2]
        p95 = samples_sorted[int(n * 0.95) - 1 if n > 1 else 0]
        return {"p50": p50, "p95": p95}

    async def _ensure_active_or_error(self) -> bool:
        if self.phase not in {"listen", "respond"} or not self.started_at:
            await self.ws.send_json(
                {
                    "type": "error",
                    "session_id": self.session_id,
                    "message": "session_not_started",
                }
            )
            return False
        return True

    def _reset_buffers(self) -> None:
        self.audio_chunks.clear()
        self.energy_history.clear()
        self.peak_energy = 0.0
        self.last_energy_ms = 0
        self.remote_cache_text = ""
        self.partial_transcript.clear()
        self.phase = "closed"
@app.get("/")
async def root():
    """根路徑"""
    return {
        "message": "黃蓉語音系統 API v2.0",
        "endpoints": {
            "POST /api/voice/huangrong": "產生語音並回傳 URL",
            "POST /api/voice/huangrong/stream": "直接返回音訊流"
        }
    }


@app.post(
    "/api/voice/huangrong",
    response_model=VoiceResponse,
    dependencies=[Depends(verify_api_key), Depends(enforce_rate_limit)],
)
async def generate_voice_api(request: VoiceRequest, http_request: Request):
    """
    產生語音並回傳下載 URL
    
    範例請求：
    ```json
    {
        "text": "你今天看起來心情不錯唷～",
        "provider": "openai",
        "emotion_auto": true
    }
    ```
    """
    try:
        # 1. 判斷語氣（如果需要）
        if request.emotion_auto:
            tagged_text = llm_emotion_route(
                request.text,
                provider=request.provider,
                fallback_to_rule=True
            )
        else:
            tagged_text = request.text

        voice_id = request.voice_id or VOICE_ID
        if not voice_id:
            raise HTTPException(status_code=500, detail="未設定 Voice ID")

        tags = extract_tags_from_text(tagged_text)
        cache_key = generate_audio_key(request.text, voice_id, tags)
        cache_path = get_cached_audio_path(cache_key)
        cache_hit = is_cache_valid(cache_path)

        if cache_hit:
            audio_filename = cache_path.name
            audio_url = f"{BASE_URL}/audio/{audio_filename}"
            logger.info(
                "voice cache hit",
                extra={
                    "path": http_request.url.path,
                    "cache_hit": True,
                    "tags": tags,
                    "text_preview": request.text[:40],
                },
            )
            return VoiceResponse(
                status="success",
                audio_url=audio_url,
                text=request.text,
                tagged_text=tagged_text,
                voice_tags=tags,
                cache_hit=True,
                message="語音產生成功（快取）"
            )

        # 2. 呼叫 ElevenLabs API（含重試）
        payload = {
            "model_id": "eleven_turbo_v2_5",
            "text": tagged_text,
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.8,
                "style": 0.9,
                "use_speaker_boost": True
            }
        }
        try:
            start_time = time.time()
            response = call_elevenlabs_generate(payload, voice_id)
            elapsed = time.time() - start_time
            with open(cache_path, "wb") as f:
                f.write(response.content)

            audio_url = f"{BASE_URL}/audio/{cache_path.name}"
            clean_expired_cache()

            logger.info(
                "voice generated",
                extra={
                    "path": http_request.url.path,
                    "cache_hit": False,
                    "elevenlabs_latency_ms": int(elapsed * 1000),
                    "tags": tags,
                    "text_preview": request.text[:40],
                },
            )

            return VoiceResponse(
                status="success",
                audio_url=audio_url,
                text=request.text,
                tagged_text=tagged_text,
                voice_tags=tags,
                cache_hit=False,
                message="語音產生成功"
            )

        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("ElevenLabs 產生語音失敗，改用 fallback", exc_info=exc)
            return VoiceResponse(
                status="fallback",
                audio_url=None,
                text=request.text,
                tagged_text=tagged_text,
                voice_tags=tags,
                cache_hit=False,
                message="語音服務暫時不可用，小軟改以文字回覆"
            )
        
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("generate_voice_api 發生未預期錯誤")
        raise HTTPException(status_code=500, detail=f"發生錯誤：{str(e)}")


@app.post(
    "/api/voice/huangrong/stream",
    dependencies=[Depends(verify_api_key), Depends(enforce_rate_limit)],
)
async def generate_voice_stream(request: VoiceRequest, http_request: Request):
    """直接返回音訊流（Streaming Response）。"""
    try:
        if request.emotion_auto:
            tagged_text = llm_emotion_route(
                request.text,
                provider=request.provider,
                fallback_to_rule=True
            )
        else:
            tagged_text = request.text

        voice_id = request.voice_id or VOICE_ID
        if not voice_id:
            raise HTTPException(status_code=500, detail="未設定 Voice ID")

        payload = {
            "model_id": "eleven_turbo_v2_5",
            "text": tagged_text,
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.8,
                "style": 0.9,
                "use_speaker_boost": True
            }
        }

        try:
            start_time = time.time()
            response = call_elevenlabs_stream(payload, voice_id)
            elapsed = time.time() - start_time
            logger.info(
                "voice stream generated",
                extra={
                    "path": http_request.url.path,
                    "elevenlabs_latency_ms": int(elapsed * 1000),
                    "tags": extract_tags_from_text(tagged_text),
                },
            )

            return StreamingResponse(
                response.iter_content(chunk_size=8192),
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition": f'attachment; filename="huangrong_audio.mp3"'
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("ElevenLabs stream 生成失敗", exc_info=exc)
            raise HTTPException(status_code=502, detail="語音服務暫時不可用")

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("generate_voice_stream 發生未預期錯誤")
        raise HTTPException(status_code=500, detail=f"發生錯誤：{str(e)}")


@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    """提供音訊檔案下載"""
    filepath = AUDIO_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="檔案不存在")
    
    from fastapi.responses import FileResponse
    return FileResponse(filepath, media_type="audio/mpeg")


@app.get("/health")
async def health_check():
    """健康檢查"""
    return {
        "status": "healthy",
        "api_key_set": bool(API_KEY),
        "voice_id_set": bool(VOICE_ID)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
