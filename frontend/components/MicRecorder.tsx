import React, { useCallback, useEffect, useRef, useState } from "react";

const SERVICE_API_KEY =
  import.meta.env.VITE_SERVICE_API_KEY || "RIUvXLm99TG_jOyN6gP1vTYE1fdmXyMxL5tLDzMwFiA";

const stripTrailingSlash = (value: string) => value.replace(/\/+$/, "");

const resolveApiBase = () => {
  const envBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (envBase) {
    return stripTrailingSlash(envBase);
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

type WhisperMessage =
  | { type: "ready" }
  | { type: "final"; text: string }
  | { type: "error"; message: string };

type MicRecorderProps = {
  onVoiceTagsChange?: (tags: string[]) => void;
  onSpeakingChange?: (speaking: boolean) => void;
};

type TranscriptEntry = {
  id: string;
  type: WhisperMessage["type"];
  text: string;
};

const MicRecorder: React.FC<MicRecorderProps> = ({ onVoiceTagsChange, onSpeakingChange }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState<string>("尚未連線");
  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([]);
  const [isGeneratingVoice, setIsGeneratingVoice] = useState(false);
  const [voiceAudioSrc, setVoiceAudioSrc] = useState<string | null>(null);
  const [voiceTags, setVoiceTags] = useState<string[]>([]);
  const [voiceMessage, setVoiceMessage] = useState<string>("");
  const [isVoicePlaying, setIsVoicePlaying] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    onVoiceTagsChange?.(voiceTags);
  }, [voiceTags, onVoiceTagsChange]);

  useEffect(() => {
    onSpeakingChange?.(isVoicePlaying || isRecording || isGeneratingVoice);
  }, [isVoicePlaying, isRecording, isGeneratingVoice, onSpeakingChange]);

  const appendTranscript = useCallback((entry: TranscriptEntry) => {
    setTranscripts((prev) => [...prev, entry]);
  }, []);

  const triggerTTS = useCallback(async (text: string) => {
    if (!text.trim()) return;

    setIsGeneratingVoice(true);
    setVoiceMessage("正在生成語音...");
    setVoiceTags([]);

    try {
      const response = await fetch(buildHttpUrl("/api/voice/huangrong"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Service-Api-Key": SERVICE_API_KEY,
        },
        body: JSON.stringify({ text, emotion_auto: true }),
      });

      if (!response.ok) {
        const errorBody = await response.text();
        throw new Error(`語音 API 失敗：${response.status} ${errorBody}`);
      }

      const data = await response.json();
      setVoiceAudioSrc(data.audio_url || null);
      setVoiceTags(data.voice_tags || []);
      setVoiceMessage(data.message || "語音已產生");
      setIsVoicePlaying(false);
    } catch (error) {
      console.error("產生語音失敗", error);
      setVoiceAudioSrc(null);
      setVoiceMessage(error instanceof Error ? error.message : "語音產生失敗");
      setVoiceTags([]);
    } finally {
      setIsGeneratingVoice(false);
    }
  }, []);

  const stopAll = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    wsRef.current?.close();
    wsRef.current = null;

    setIsRecording(false);
    setStatus("已停止錄音");
    setIsVoicePlaying(false);
  }, []);

  const handleWebSocketMessage = useCallback(
    (event: MessageEvent) => {
      let data: WhisperMessage;
      try {
        data = JSON.parse(event.data);
      } catch (error) {
        console.error("無法解析 Whisper 訊息", error);
        return;
      }

      if (data.type === "ready") {
        setStatus("Whisper 連線成功，開始錄音");
        appendTranscript({ id: crypto.randomUUID(), type: "ready", text: "Whisper 服務已就緒" });
        return;
      }

      if (data.type === "final") {
        appendTranscript({ id: crypto.randomUUID(), type: "final", text: data.text });
        triggerTTS(data.text);
        return;
      }

      if (data.type === "error") {
        appendTranscript({ id: crypto.randomUUID(), type: "error", text: data.message });
        setStatus(`Whisper 發生錯誤: ${data.message}`);
        stopAll();
      }
    },
    [appendTranscript, stopAll, triggerTTS]
  );

  const startRecording = useCallback(async () => {
    if (isRecording) {
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const params = new URLSearchParams({ service_api_key: SERVICE_API_KEY });
      const wsUrl = buildWebSocketUrl("/api/whisper", params);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus("已連線 Whisper，準備錄音...");
        const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
        recorderRef.current = recorder;

        recorder.addEventListener("dataavailable", async (event) => {
          if (event.data.size === 0 || ws.readyState !== WebSocket.OPEN) return;

          try {
            const buffer = await event.data.arrayBuffer();
            ws.send(buffer);
          } catch (error) {
            console.error("傳送音訊片段失敗", error);
          }
        });

        recorder.start(1000); // 每秒產出一個 chunk
        setIsRecording(true);
        setStatus("錄音中... 點擊停止以結束");
      };

      ws.onerror = (event) => {
        console.error("Whisper WebSocket 錯誤", event);
        setStatus("Whisper WebSocket 錯誤");
        stopAll();
      };

      ws.onmessage = handleWebSocketMessage;
      ws.onclose = () => {
        setStatus("Whisper 連線關閉");
        stopAll();
      };
    } catch (error) {
      console.error("取得麥克風權限失敗", error);
      setStatus("取得麥克風權限失敗，請允許存取");
    }
  }, [handleWebSocketMessage, isRecording, stopAll]);

  const stopRecording = useCallback(() => {
    stopAll();
  }, [stopAll]);

  useEffect(() => {
    return () => {
      stopAll();
    };
  }, [stopAll]);

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
          <div key={entry.id} className={`transcript transcript-${entry.type}`}>
            <span className="transcript-label">[{entry.type}]</span>
            <span className="transcript-text">{entry.text}</span>
          </div>
        ))}
      </div>

      <div className="voice-output">
        <h3>小軟語音回應</h3>
        {isGeneratingVoice && <p className="voice-status">🔄 {voiceMessage || "語音生成中..."}</p>}
        {!isGeneratingVoice && voiceMessage && <p className="voice-status">✅ {voiceMessage}</p>}
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

