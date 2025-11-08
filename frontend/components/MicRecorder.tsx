import React, { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE_URL, SERVICE_API_KEY } from "../utils/config";

const arrayBufferToBase64 = (buffer: ArrayBuffer): string => {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
};

const stripTrailingSlash = (value: string) => value.replace(/\/+$/, "");

const MIME_PREFERENCE_ORDER = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/ogg",
  "audio/mp4;codecs=opus",
  "audio/mp4"
] as const;

const getSupportedMimeType = (): string | undefined => {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) {
    return undefined;
  }
  for (const candidate of MIME_PREFERENCE_ORDER) {
    if (MediaRecorder.isTypeSupported(candidate)) {
      return candidate;
    }
  }
  return undefined;
};

const resolveApiBase = () => {
  if (API_BASE_URL) {
    return stripTrailingSlash(API_BASE_URL);
  }
  if (typeof window !== "undefined") {
    return stripTrailingSlash(window.location.origin);
  }
  return "";
};

const buildHttpUrl = (path: string) => {
  const base = resolveApiBase();
  if (!base) {
    return path;
  }
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return new URL(normalizedPath, `${base}/`).toString();
};

const buildWebSocketUrl = (path: string, params: URLSearchParams) => {
  const base = resolveApiBase() || (typeof window !== "undefined" ? window.location.origin : "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(normalizedPath, `${base}/`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  params.forEach((value, key) => {
    url.searchParams.set(key, value);
  });
  return url.toString();
};

type RoleStatus = {
  roleId: string;
  status: string;
  message?: string;
  latencyMs?: number;
  previousRole?: string;
  phase?: string;
};

type MicRecorderProps = {
  onVoiceTagsChange?: (tags: string[]) => void;
  onSpeakingChange?: (speaking: boolean) => void;
  onRealtimeMetricsChange?: (metrics: {
    avgEnergy: number;
    peakEnergy: number;
    emotion?: string;
    pitchHz?: number;
  }) => void;
  roleId: string;
  onRoleStatusChange?: (status: RoleStatus) => void;
};

type TranscriptEntry = {
  id: string;
  role: "system" | "user" | "assistant" | "error";
  text: string;
  isFinal?: boolean;
};

const mapTagsToEmotion = (tags: string[]): string | undefined => {
  const normalized = tags.map((tag) => tag.toLowerCase());
  const match = [
    { keywords: ["angry", "furious", "power"], emotion: "angry" },
    { keywords: ["cry", "sad", "tear", "sigh"], emotion: "sad" },
    { keywords: ["happy", "excited", "laugh"], emotion: "happy" },
    { keywords: ["soft", "whisper", "gentle"], emotion: "soft" },
    { keywords: ["curious", "wonder"], emotion: "curious" },
  ].find((entry) => entry.keywords.some((keyword) => normalized.some((tag) => tag.includes(keyword))));
  return match?.emotion;
};

const MicRecorder: React.FC<MicRecorderProps> = ({
  onVoiceTagsChange,
  onSpeakingChange,
  onRealtimeMetricsChange,
  roleId,
  onRoleStatusChange,
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState<string>("尚未連線");
  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([]);
  const [isStreamingReply, setIsStreamingReply] = useState(false);
  const [voiceAudioSrc, setVoiceAudioSrc] = useState<string | null>(null);
  const [voiceTags, setVoiceTags] = useState<string[]>([]);
  const [voiceMessage, setVoiceMessage] = useState<string>("");
  const [isVoicePlaying, setIsVoicePlaying] = useState(false);
  const [assistantText, setAssistantText] = useState<string>("");

  const wsRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const ttsChunksRef = useRef<Uint8Array[]>([]);
  const audioUrlRef = useRef<string | null>(null);
  const currentUserTranscriptIdRef = useRef<string | null>(null);
  const latestEnergyRef = useRef<{ avg: number; peak: number }>({ avg: 0, peak: 0 });
  const sessionIdRef = useRef<string | null>(null);
  const roleRef = useRef<string | null>(null);
  const pendingSwitchRef = useRef<string | null>(null);

  const resetTtsPlayback = useCallback(() => {
    ttsChunksRef.current = [];
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    setVoiceAudioSrc(null);
  }, []);

  const pushTtsChunk = useCallback((base64Chunk: string) => {
    try {
      const binary = Uint8Array.from(atob(base64Chunk), (char) => char.charCodeAt(0));
      ttsChunksRef.current.push(binary);
    } catch (error) {
      console.error("解析 TTS chunk 失敗", error);
    }
  }, []);

  const finalizeTtsPlayback = useCallback(() => {
    if (ttsChunksRef.current.length === 0) {
      return;
    }
    const blob = new Blob(ttsChunksRef.current, { type: "audio/mpeg" });
    const url = URL.createObjectURL(blob);
    audioUrlRef.current = url;
    setVoiceAudioSrc(url);
    setVoiceMessage("語音已準備播放");
    ttsChunksRef.current = [];
  }, []);

  useEffect(() => {
    onVoiceTagsChange?.(voiceTags);
  }, [voiceTags, onVoiceTagsChange]);

  useEffect(() => {
    onSpeakingChange?.(isVoicePlaying || isRecording || isStreamingReply);
  }, [isVoicePlaying, isRecording, isStreamingReply, onSpeakingChange]);

  const appendTranscript = useCallback((entry: TranscriptEntry) => {
    setTranscripts((prev) => [...prev, entry]);
  }, []);

  const upsertUserTranscript = useCallback((text: string, isFinal: boolean) => {
    setTranscripts((prev) => {
      let targetId = currentUserTranscriptIdRef.current;
      if (!targetId) {
        targetId = crypto.randomUUID();
        currentUserTranscriptIdRef.current = targetId;
        return [...prev, { id: targetId, role: "user", text, isFinal }];
      }
      let updated = false;
      const next = prev.map((item) => {
        if (item.id === targetId) {
          updated = true;
          return { ...item, text, isFinal };
        }
        return item;
      });
      if (!updated) {
        next.push({ id: targetId, role: "user", text, isFinal });
      }
      return next;
    });
    if (isFinal) {
      currentUserTranscriptIdRef.current = null;
    }
  }, []);

  const appendAssistantTranscript = useCallback((text: string) => {
    setTranscripts((prev) => [...prev, { id: crypto.randomUUID(), role: "assistant", text, isFinal: true }]);
  }, []);

  const stopAll = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(
          JSON.stringify({
            type: "voice.end",
            session_id: sessionIdRef.current ?? undefined,
          })
        );
      } catch {
        // ignore
      }
    }
    wsRef.current?.close();
    wsRef.current = null;

    setIsRecording(false);
    setStatus("已停止錄音");
    setIsVoicePlaying(false);
    setIsStreamingReply(false);
    resetTtsPlayback();
    sessionIdRef.current = null;
    roleRef.current = null;
    pendingSwitchRef.current = null;
  }, [resetTtsPlayback]);

  const handleWebSocketMessage = useCallback(
    (event: MessageEvent) => {
      let payload: any;
      try {
        payload = JSON.parse(event.data);
      } catch (error) {
        console.error("無法解析 Gateway 訊息", error);
        return;
      }

      const type = payload?.type;
      switch (type) {
        case "gateway.ready":
          setStatus("Gateway 已就緒，等待 voice.ack...");
          appendTranscript({ id: crypto.randomUUID(), role: "system", text: "Gateway 已就緒" });
          break;
        case "voice.ack":
          sessionIdRef.current = typeof payload.session_id === "string" ? payload.session_id : sessionIdRef.current;
          if (typeof payload.role_id === "string") {
            roleRef.current = payload.role_id;
            onRoleStatusChange?.({
              roleId: payload.role_id,
              status: "active",
              message: "session_started",
              latencyMs: 0,
              phase: typeof payload.phase === "string" ? payload.phase : "listen",
            });
          }
          setStatus("Session 已啟動，開始串流音訊");
          appendTranscript({
            id: crypto.randomUUID(),
            role: "system",
            text: `Session 啟動：${sessionIdRef.current ?? "unknown"}`,
          });
          break;
        case "voice.role_status": {
          const statusPayload: RoleStatus = {
            roleId: typeof payload.role_id === "string" ? payload.role_id : roleRef.current ?? roleId,
            status: typeof payload.status === "string" ? payload.status : "unknown",
            message: typeof payload.message === "string" ? payload.message : undefined,
            latencyMs: typeof payload.latency_ms === "number" ? payload.latency_ms : undefined,
            previousRole: typeof payload.previous_role === "string" ? payload.previous_role : undefined,
            phase: typeof payload.phase === "string" ? payload.phase : undefined,
          };
          if (statusPayload.status === "active") {
            roleRef.current = statusPayload.roleId;
            pendingSwitchRef.current = null;
          } else if (statusPayload.status === "error") {
            pendingSwitchRef.current = null;
          }
          onRoleStatusChange?.(statusPayload);
          break;
        }
        case "metrics": {
          const avg =
            typeof payload.avg_energy === "number"
              ? payload.avg_energy
              : typeof payload.avgEnergy === "number"
                ? payload.avgEnergy
                : undefined;
          const peak =
            typeof payload.peak_energy === "number"
              ? payload.peak_energy
              : typeof payload.peakEnergy === "number"
                ? payload.peakEnergy
                : undefined;
          const emotionEstimate =
            typeof payload.emotion_estimate === "string"
              ? payload.emotion_estimate
              : typeof payload.emotionEstimate === "string"
                ? payload.emotionEstimate
                : undefined;
          const pitch =
            typeof payload.pitch_hz === "number"
              ? payload.pitch_hz
              : typeof payload.pitchHz === "number"
                ? payload.pitchHz
                : undefined;

          if (avg !== undefined || peak !== undefined || emotionEstimate !== undefined || pitch !== undefined) {
            const nextAvg = avg ?? latestEnergyRef.current.avg;
            const nextPeak = peak ?? latestEnergyRef.current.peak;
            latestEnergyRef.current = { avg: nextAvg, peak: nextPeak };
            onRealtimeMetricsChange?.({
              avgEnergy: nextAvg,
              peakEnergy: nextPeak,
              emotion: emotionEstimate,
              pitchHz: pitch,
            });
          }

          if (typeof payload.transcript === "string" && payload.transcript.trim()) {
            const isFinal = Boolean(payload.is_final ?? payload.isFinal);
            upsertUserTranscript(payload.transcript, isFinal);
            setStatus(isFinal ? "等待小軟回應..." : "錄音中...");
            if (isFinal) {
              setIsStreamingReply(true);
            }
          }
          break;
        }
        case "assistant.reply": {
          const replyText = typeof payload.text === "string" ? payload.text : "";
          const tags = Array.isArray(payload.tags) ? payload.tags : [];
          setAssistantText(replyText);
          appendAssistantTranscript(replyText);
          setVoiceTags(tags);
          const derivedEmotion = mapTagsToEmotion(tags);
          if (derivedEmotion) {
            onRealtimeMetricsChange?.({
              avgEnergy: latestEnergyRef.current.avg,
              peakEnergy: latestEnergyRef.current.peak,
              emotion: derivedEmotion,
            });
          }
          setVoiceMessage("語音生成中...");
          setIsStreamingReply(true);
          resetTtsPlayback();
          setStatus("小軟正在準備語音回應...");
          break;
        }
        case "tts.stream": {
          const chunk = payload.chunk;
          if (typeof chunk === "string") {
            pushTtsChunk(chunk);
            setVoiceMessage("語音串流輸入中...");
          }
          break;
        }
        case "tts.stream.completed":
          finalizeTtsPlayback();
          setIsStreamingReply(false);
          setStatus("小軟語音回應完成");
          break;
        case "session.closed":
          sessionIdRef.current = null;
          roleRef.current = null;
          pendingSwitchRef.current = null;
          setIsStreamingReply(false);
          setStatus(`Session 結束：${payload.reason ?? "completed"}`);
          appendTranscript({
            id: crypto.randomUUID(),
            role: "system",
            text: `Session 結束 (${payload.reason ?? "completed"})`,
          });
          break;
        case "error":
          appendTranscript({
            id: crypto.randomUUID(),
            role: "error",
            text: typeof payload.message === "string" ? payload.message : "未知錯誤",
          });
          setStatus(`Gateway 發生錯誤: ${payload.message ?? "unknown"}`);
          setIsStreamingReply(false);
          stopAll();
          break;
        default:
          break;
      }
    },
    [
      appendAssistantTranscript,
      appendTranscript,
      finalizeTtsPlayback,
      roleId,
      onRealtimeMetricsChange,
      onRoleStatusChange,
      pushTtsChunk,
      resetTtsPlayback,
      stopAll,
      upsertUserTranscript,
    ]
  );

  const startRecording = useCallback(async () => {
    if (isRecording) {
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = getSupportedMimeType();
      const params = new URLSearchParams({
        service_api_key: SERVICE_API_KEY
      });
      if (mimeType) {
        params.set("mime_type", mimeType);
      }

      resetTtsPlayback();
      setVoiceTags([]);
      setVoiceMessage("");
      setAssistantText("");

      const wsUrl = buildWebSocketUrl("/api/voice/stream", params);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        sessionIdRef.current = null;
        roleRef.current = null;
        pendingSwitchRef.current = roleId;
        setStatus("已連線 Gateway，準備啟動 session...");
        const recorderOptions = mimeType ? { mimeType } : undefined;
        const recorder = new MediaRecorder(stream, recorderOptions);
        recorderRef.current = recorder;

        ws.send(
          JSON.stringify({
            type: "voice.start",
            role_id: roleId,
            voice_id: undefined,
            provider: "openai",
            mime_type: mimeType,
            timestamp: Date.now(),
          })
        );

        recorder.addEventListener("dataavailable", async (event) => {
          if (event.data.size === 0 || ws.readyState !== WebSocket.OPEN) return;

          try {
            const buffer = await event.data.arrayBuffer();
            const chunk = arrayBufferToBase64(buffer);
            ws.send(
              JSON.stringify({
                type: "voice.data",
                session_id: sessionIdRef.current ?? undefined,
                chunk,
                timestamp: Date.now(),
              })
            );
          } catch (error) {
            console.error("傳送音訊片段失敗", error);
          }
        });

        recorder.start(500); // 每 0.5 秒一個 chunk，降低延遲
        setIsRecording(true);
        setStatus("錄音中... 點擊停止以結束");
      };

      ws.onerror = (event) => {
        console.error("Gateway WebSocket 錯誤", event);
        setStatus("Gateway WebSocket 錯誤");
        stopAll();
      };

      ws.onmessage = handleWebSocketMessage;
      ws.onclose = () => {
        sessionIdRef.current = null;
        if (isRecording) {
          stopAll();
        } else {
          setStatus("Gateway 連線關閉");
        }
      };
    } catch (error) {
      console.error("取得麥克風權限失敗", error);
      setStatus("取得麥克風權限失敗，請允許存取");
    }
  }, [handleWebSocketMessage, isRecording, resetTtsPlayback, roleId, stopAll]);

  const stopRecording = useCallback(() => {
    stopAll();
  }, [stopAll]);

  useEffect(() => {
    return () => {
      stopAll();
    };
  }, [stopAll]);

  useEffect(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      return;
    }
    if (!roleId) {
      return;
    }
    if (roleRef.current === roleId || pendingSwitchRef.current === roleId) {
      return;
    }
    pendingSwitchRef.current = roleId;
    ws.send(
      JSON.stringify({
        type: "voice.switch",
        role_id: roleId,
      })
    );
  }, [roleId]);

  return (
    <div className="mic-recorder">
      <div className="controls">
        <button onClick={startRecording} disabled={isRecording}>
          🎙️ 開始錄音
        </button>
        <button onClick={stopRecording} disabled={!isRecording}>
          ⏹ 停止
        </button>
      </div>
      <p className="status">{status}</p>

      <div className="transcripts">
        {transcripts.map((entry) => (
          <div key={entry.id} className={`transcript transcript-${entry.role}`}>
            <span className="transcript-label">
              {entry.role === "user" && "[你]"}
              {entry.role === "assistant" && "[小軟]"}
              {entry.role === "system" && "[系統]"}
              {entry.role === "error" && "[錯誤]"}
            </span>
            <span className="transcript-text">
              {entry.text}
              {entry.isFinal === false && " (聆聽中…)"}
            </span>
          </div>
        ))}
      </div>

      <div className="voice-output">
        <h3>小軟語音回應</h3>
        {isStreamingReply && <p className="voice-status">🔄 {voiceMessage || "語音生成中..."}</p>}
        {!isStreamingReply && voiceMessage && <p className="voice-status">✅ {voiceMessage}</p>}
        {assistantText && <p className="assistant-text">💬 {assistantText}</p>}
        {voiceTags.length > 0 && (
          <p className="voice-tags">
            語氣標籤：{voiceTags.map((tag) => (
              <span key={tag} className="voice-tag">{tag}</span>
            ))}
          </p>
        )}
        {voiceAudioSrc && (
          <audio
            key={voiceAudioSrc}
            controls
            autoPlay
            src={voiceAudioSrc}
            className="voice-audio"
            onPlay={() => setIsVoicePlaying(true)}
            onPause={() => setIsVoicePlaying(false)}
            onEnded={() => setIsVoicePlaying(false)}
          />
        )}
      </div>
    </div>
  );
};

export default MicRecorder;

