import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import MicRecorder from "../components/MicRecorder";
import LiquidSphere from "../components/LiquidSphere";
import "../styles/mic-recorder.css";
import { API_BASE_URL, CHATKIT_SESSION_ENDPOINT, SERVICE_API_KEY } from "../utils/config";

type RoleStatus = {
  roleId: string;
  status: string;
  message?: string;
  latencyMs?: number;
  previousRole?: string;
  phase?: string;
};

const ROLE_OPTIONS = [
  { id: "huangrong", label: "黃蓉", emoji: "🌸" },
  { id: "xiaoruan", label: "小軟", emoji: "🎐" },
  { id: "pipi", label: "皮皮", emoji: "🪄" },
] as const;

const VoiceChat: React.FC = () => {
  const [emotionTags, setEmotionTags] = useState<string[]>([]);
  const [isMicActive, setIsMicActive] = useState(false);
  const [isChatKitPlaying, setIsChatKitPlaying] = useState(false);
  const isSpeaking = isMicActive || isChatKitPlaying;
  const [visualMetrics, setVisualMetrics] = useState<{ avg: number; peak: number; emotion: string }>({
    avg: 0,
    peak: 0,
    emotion: "neutral",
  });
  const [latestMetrics, setLatestMetrics] = useState<{
    avgEnergy: number;
    peakEnergy: number;
    emotion?: string;
    pitchHz?: number;
  }>({
    avgEnergy: 0,
    peakEnergy: 0,
  });
  const [showEmotionDebug, setShowEmotionDebug] = useState(false);
  const [activeRoleId, setActiveRoleId] = useState<string>(ROLE_OPTIONS[0].id);
  const [requestedRoleId, setRequestedRoleId] = useState<string>(ROLE_OPTIONS[0].id);
  const [roleStatus, setRoleStatus] = useState<RoleStatus | null>(null);
  const chatkitSecretRef = useRef<string | null>(null);
  const assistantBufferRef = useRef("");
  const chatkitAudioRef = useRef<{ audio: HTMLAudioElement | null; url: string | null }>({
    audio: null,
    url: null,
  });

  const buildApiUrl = useCallback((path: string) => {
    if (!API_BASE_URL) {
      return path;
    }
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    return new URL(normalizedPath, `${API_BASE_URL.replace(/\/+$/, "")}/`).toString();
  }, []);

  const cleanupChatkitAudio = useCallback(() => {
    if (chatkitAudioRef.current.audio) {
      chatkitAudioRef.current.audio.pause();
    }
    if (chatkitAudioRef.current.url) {
      URL.revokeObjectURL(chatkitAudioRef.current.url);
    }
    chatkitAudioRef.current = { audio: null, url: null };
  }, []);

  const playAssistantVoice = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) {
        return;
      }
      try {
        cleanupChatkitAudio();
        setIsChatKitPlaying(true);
        setVisualMetrics((prev) => ({
          avg: Math.max(prev.avg, 55),
          peak: Math.max(prev.peak, 75),
          emotion: prev.emotion,
        }));
        const response = await fetch(buildApiUrl("/api/voice/huangrong/stream"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Service-Api-Key": SERVICE_API_KEY,
          },
          body: JSON.stringify({ text: trimmed, emotion_auto: true }),
        });
        if (!response.ok) {
          throw new Error(`TTS error: ${response.status}`);
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        chatkitAudioRef.current = { audio, url };
        audio.onended = () => {
          cleanupChatkitAudio();
          setIsChatKitPlaying(false);
          setVisualMetrics((prev) => ({
            ...prev,
            avg: prev.avg * 0.6,
            peak: prev.peak * 0.6,
          }));
        };
        audio.onerror = () => {
          cleanupChatkitAudio();
          setIsChatKitPlaying(false);
          setVisualMetrics((prev) => ({
            ...prev,
            avg: prev.avg * 0.6,
            peak: prev.peak * 0.6,
          }));
        };
        await audio.play();
      } catch (error) {
        console.error("播放 ChatKit 語音失敗", error);
        cleanupChatkitAudio();
        setIsChatKitPlaying(false);
      }
    },
    [buildApiUrl, cleanupChatkitAudio]
  );

  const fetchClientSecret = useCallback(async () => {
    if (chatkitSecretRef.current) {
      return chatkitSecretRef.current;
    }
    const response = await fetch(CHATKIT_SESSION_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Service-Api-Key": SERVICE_API_KEY,
      },
      body: JSON.stringify({ service_key: SERVICE_API_KEY }),
    });
    if (!response.ok) {
      throw new Error(`取得 ChatKit Client Secret 失敗: ${response.status}`);
    }
    const data = await response.json();
    chatkitSecretRef.current = data.client_secret;
    return data.client_secret as string;
  }, []);

  const dominantEmotion = useMemo(() => {
    const tagLower = emotionTags.map((tag) => tag.toLowerCase());
    const match = [
      { keywords: ["angry", "furious", "power"], emotion: "angry" },
      { keywords: ["cry", "sad", "tear", "sigh"], emotion: "sad" },
      { keywords: ["happy", "excited", "laugh", "cheer"], emotion: "happy" },
      { keywords: ["soft", "whisper", "gentle"], emotion: "soft" },
      { keywords: ["curious", "wonder"], emotion: "curious" },
    ].find((entry) => entry.keywords.some((keyword) => tagLower.some((tag) => tag.includes(keyword))));
    const energyEmotion = visualMetrics.emotion;
    return (match?.emotion ?? energyEmotion ?? "neutral").toLowerCase();
  }, [emotionTags, visualMetrics.emotion]);

  const speakingEnergy = visualMetrics.avg > 0 ? visualMetrics.avg : isSpeaking ? 45 : 5;
  const playbackEnergy = visualMetrics.peak > 0 ? visualMetrics.peak : isSpeaking ? 40 : 5;
  const handleRealtimeMetrics = useCallback(
    (metrics: { avgEnergy: number; peakEnergy: number; emotion?: string; pitchHz?: number }) => {
      setVisualMetrics((prev) => ({
        avg: metrics.avgEnergy ?? prev.avg,
        peak: metrics.peakEnergy ?? prev.peak,
        emotion: metrics.emotion ? metrics.emotion.toLowerCase() : prev.emotion,
      }));
      setLatestMetrics((prev) => ({
        avgEnergy: metrics.avgEnergy ?? prev.avgEnergy,
        peakEnergy: metrics.peakEnergy ?? prev.peakEnergy,
        emotion: metrics.emotion ?? prev.emotion,
        pitchHz: metrics.pitchHz ?? prev.pitchHz,
      }));
    },
    []
  );
  const handleRoleStatusChange = useCallback((status: RoleStatus) => {
    setRoleStatus(status);
    if (status.status === "active") {
      setActiveRoleId(status.roleId);
    }
  }, []);
  const handleRoleSelect = useCallback((roleIdValue: string) => {
    setRequestedRoleId(roleIdValue);
    setRoleStatus((prev) => ({
      roleId: roleIdValue,
      status: "switching",
      message: prev?.message,
    }));
  }, []);
  const toggleEmotionDebug = useCallback(() => setShowEmotionDebug((prev) => !prev), []);

  const chatkitOptions = useMemo(
    () => ({
      api: {
        getClientSecret: async () => fetchClientSecret(),
      },
      theme: { colorScheme: "dark" as const },
      header: { title: { text: "靈芽 ChatKit" } },
      history: { enabled: false },
      startScreen: {
        greeting: "和小軟聊聊或直接輸入提示開始互動",
        prompts: ["介紹一下你今天的心情", "問問小軟最近的靈氣", "請小軟唱一段歌"],
      },
      composer: { placeholder: "輸入訊息，或直接開始說話..." },
    }),
    [fetchClientSecret]
  );
  const activeRoleOption = useMemo(
    () => ROLE_OPTIONS.find((option) => option.id === activeRoleId) ?? ROLE_OPTIONS[0],
    [activeRoleId]
  );
  const requestedRoleOption = useMemo(
    () => ROLE_OPTIONS.find((option) => option.id === requestedRoleId) ?? ROLE_OPTIONS[0],
    [requestedRoleId]
  );
  const roleIndicator = useMemo(() => {
    if (!roleStatus) {
      return "等待角色狀態...";
    }
    const latency = typeof roleStatus.latencyMs === "number" ? `${roleStatus.latencyMs} ms` : "";
    if (roleStatus.status === "active") {
      return `${activeRoleOption.emoji} ${activeRoleOption.label} 就緒 ${latency ? `(${latency})` : ""}`.trim();
    }
    if (roleStatus.status === "error") {
      return `⚠️ 切換失敗：${roleStatus.message ?? "未知錯誤"}`;
    }
    if (roleStatus.status === "switching") {
      return `🌀 正在切換至 ${requestedRoleOption.label}...`;
    }
    return `${requestedRoleOption.label} 狀態：${roleStatus.status}`;
  }, [roleStatus, activeRoleOption, requestedRoleOption]);

  const { control: chatkitControl, ref: chatkitRef } = useChatKit(chatkitOptions);

  useEffect(() => {
    const element = chatkitRef.current;
    if (!element) {
      return;
    }

    const handleLog = (event: Event) => {
      const detail = (event as CustomEvent<any>).detail;
      if (!detail) {
        return;
      }
      const { name, data } = detail;
      if (typeof data?.delta === "string") {
        assistantBufferRef.current += data.delta;
      } else if (typeof data?.text === "string") {
        assistantBufferRef.current = data.text;
      } else if (typeof data?.message === "string") {
        assistantBufferRef.current = data.message;
      } else if (Array.isArray(data?.chunks)) {
        const chunkText = data.chunks
          .map((chunk: any) => {
            if (typeof chunk === "string") return chunk;
            if (chunk && typeof chunk.text === "string") return chunk.text;
            return "";
          })
          .join("");
        if (chunkText.trim()) {
          assistantBufferRef.current = chunkText;
        }
      }
    };

    const handleResponseEnd = () => {
      const text = assistantBufferRef.current.trim();
      assistantBufferRef.current = "";
      if (text) {
        playAssistantVoice(text);
      }
    };

    const handleError = (event: Event) => {
      console.error("ChatKit 發生錯誤", (event as CustomEvent<any>).detail);
    };

    element.addEventListener("chatkit.log", handleLog as EventListener);
    element.addEventListener("chatkit.response.end", handleResponseEnd as EventListener);
    element.addEventListener("chatkit.error", handleError as EventListener);

    return () => {
      element.removeEventListener("chatkit.log", handleLog as EventListener);
      element.removeEventListener("chatkit.response.end", handleResponseEnd as EventListener);
      element.removeEventListener("chatkit.error", handleError as EventListener);
    };
  }, [chatkitRef, playAssistantVoice]);

  useEffect(() => () => cleanupChatkitAudio(), [cleanupChatkitAudio]);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("debugEmotion") === "1") {
      setShowEmotionDebug(true);
    }
  }, []);

  return (
    <div className="voice-chat-container">
      <header className="voice-chat-header">
        <h1>🌸 花小軟語魂實境</h1>
        <p>按下錄音開始說話，小軟會即時聆聽並回應你。</p>
        <button type="button" className="emotion-debug-toggle" onClick={toggleEmotionDebug}>
          {showEmotionDebug ? "隱藏 Emotion Debug" : "顯示 Emotion Debug"}
        </button>
        <div className="role-switcher">
          <span className="role-switcher-label">語氣靈角色</span>
          <div className="role-switcher-buttons">
            {ROLE_OPTIONS.map((option) => {
              const isActive = option.id === activeRoleId;
              const isRequested = option.id === requestedRoleId && option.id !== activeRoleId;
              return (
                <button
                  key={option.id}
                  type="button"
                  className={`role-pill ${isActive ? "role-pill-active" : ""} ${
                    isRequested ? "role-pill-pending" : ""
                  }`}
                  onClick={() => handleRoleSelect(option.id)}
                  disabled={requestedRoleId === option.id && requestedRoleId !== activeRoleId}
                >
                  <span className="role-pill-emoji">{option.emoji}</span>
                  {option.label}
                </button>
              );
            })}
          </div>
          <span className="role-switcher-status">{roleIndicator}</span>
        </div>
      </header>

      <div className="voiceball-section">
        <LiquidSphere
          speakingEnergy={speakingEnergy}
          playbackEnergy={playbackEnergy}
          emotion={dominantEmotion}
        />
        <p className="voiceball-caption">
          {emotionTags.length > 0
            ? `感知情緒：${emotionTags.join("、")}`
            : `等待語氣訊號...（目前：${dominantEmotion}）`}
        </p>
      </div>

      <main className="voice-chat-main">
        <section className="voice-chat-transcript">
          <h2>即時字幕</h2>
          <MicRecorder
            onVoiceTagsChange={setEmotionTags}
            onSpeakingChange={setIsMicActive}
            onRealtimeMetricsChange={handleRealtimeMetrics}
            roleId={requestedRoleId}
            onRoleStatusChange={handleRoleStatusChange}
          />
        </section>

        <section className="voice-chat-chatkit">
          <h2>ChatKit 對話</h2>
          <div className="chatkit-wrapper">
            <ChatKit ref={chatkitRef} control={chatkitControl} className="chatkit-frame" />
          </div>
        </section>

        {showEmotionDebug && (
          <aside className="emotion-debug-panel">
            <h3>Emotion Debug Overlay</h3>
            <div className="emotion-debug-grid">
              <div>
                <span className="emotion-debug-label">Avg Energy</span>
                <span className="emotion-debug-value">{latestMetrics.avgEnergy.toFixed(2)}</span>
              </div>
              <div>
                <span className="emotion-debug-label">Peak Energy</span>
                <span className="emotion-debug-value">{latestMetrics.peakEnergy.toFixed(2)}</span>
              </div>
              <div>
                <span className="emotion-debug-label">Pitch (Hz)</span>
                <span className="emotion-debug-value">
                  {latestMetrics.pitchHz ? latestMetrics.pitchHz.toFixed(1) : "—"}
                </span>
              </div>
              <div>
                <span className="emotion-debug-label">Emotion</span>
                <span className="emotion-debug-value">{latestMetrics.emotion ?? "—"}</span>
              </div>
            </div>
          </aside>
        )}

        <aside className="voice-chat-help">
          <h3>操作提示</h3>
          <ul>
            <li>點擊「開始錄音」允許麥克風權限</li>
            <li>錄音時保持穩定語速，系統會自動斷句</li>
            <li>若出現錯誤，可重新整理或檢查 API key</li>
          </ul>
        </aside>
      </main>
    </div>
  );
};

export default VoiceChat;

