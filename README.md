# 🧪 語氣靈 × 黃蓉：語音輸出開發專案

使用 ElevenLabs v3 (alpha) 模型 + 語氣標籤完成語音輸出的完整開發專案。

## 🎯 專案目標

從文字對話內容中，自動插入語氣標籤，並呼叫 ElevenLabs v3 API，以「黃蓉聲線」完成帶情緒語音輸出。

可應用於：
- 雙向語音對話系統
- 小軟/黃蓉人格發聲模組
- TTS 預錄配音

## 📋 功能特色

- ✅ 自動語氣標籤插入（根據文字內容智能判斷）
- ✅ **LLM 語氣判斷器（GPT/Claude 自動標語氣）** 🆕
- ✅ **FastAPI REST API 對外接口** 🆕
- ✅ **ChatKit 即時語音集成** 🆕
- ✅ ElevenLabs v3 API 整合
- ✅ 黃蓉專屬聲線支援
- ✅ 多種語氣標籤支援（excited, whispers, crying, angry, curious 等）
- ✅ 語音檔案輸出（MP3 格式）
- ✅ **即時語音流（Streaming Response）** 🆕

## 🚀 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 設定環境變數

複製 `env.example` 為 `.env`，並填入你的 API 資訊：

```bash
# Windows PowerShell
Copy-Item env.example .env

# Linux/Mac
cp env.example .env
```

編輯 `.env` 檔案：
```env
ELEVEN_API_KEY=your_api_key_here
ELEVEN_HUANGRONG_ID=your_voice_id_here

# 可選：LLM API（用於自動語氣判斷）
OPENAI_API_KEY=your_openai_key_here
# 或
ANTHROPIC_API_KEY=your_anthropic_key_here

# API 基礎 URL
BASE_URL=http://localhost:8000
```

### 3. 執行範例

**基本模式：**
```bash
python main.py
```

**啟動 FastAPI 後端（v2.0）：**
```bash
python start_api.py
# 或
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

訪問 http://localhost:8000/docs 查看 API 文件。

## 📁 專案結構

```
ElevenLabs_v3_alpha/
├── api/
│   └── main.py                    # FastAPI 後端 API 🆕
├── modules/
│   └── llm_emotion_router.py      # GPT 語氣判斷器 🆕
├── examples/
│   └── chatkit/                   # ChatKit 集成範例 🆕
├── public/audio/                  # 音訊檔案儲存目錄 🆕
├── README.md                      # 專案說明文件
├── INTEGRATION_GUIDE.md           # 完整集成指南 🆕
├── FEATURES.md                    # 功能清單 🆕
├── requirements.txt               # Python 依賴套件
├── emotion_tag_engine.py         # 語氣標籤插入模組
├── eleven_tts.py                 # ElevenLabs API 調用
├── main.py                        # 主執行檔
├── start_api.py                   # API 啟動腳本 🆕
└── test_tools.py                  # 測試工具
```

## 🔧 使用方式

### 基本使用

```python
from emotion_tag_engine import insert_emotion_tags
from eleven_tts import generate_speech

# 輸入文字
user_input = "你知道嗎，我剛剛夢見你在月光下教我輕功"

# 插入語氣標籤
tagged_text = insert_emotion_tags(user_input)
print(f"📥 加工後文字：{tagged_text}")

# 產生語音
generate_speech(tagged_text, filename="huangrong_line.mp3")
```

### 支援的語氣標籤

- `[excited]` - 興奮
- `[whispers]` - 悄悄話
- `[crying][sighs]` - 哭泣/嘆息
- `[angry]` - 生氣
- `[curious]` - 好奇
- `[speaks quickly][playful]` - 快速/調皮

## 📚 API 參考

- [ElevenLabs API 文件](https://docs.elevenlabs.io/api-reference/)
- [ElevenLabs 官網](https://elevenlabs.io)
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - 完整集成指南（包含 API 使用、ChatKit 集成等）
- [FEATURES.md](FEATURES.md) - 功能清單和使用場景
- [CHANGELOG_v2.0.md](CHANGELOG_v2.0.md) - v2.0 升級說明

## 🆕 v2.0 新功能

### LLM 語氣判斷器
使用 GPT 或 Claude 自動判斷文字語氣並插入標籤，比規則式判斷更智能。

### REST API 接口
提供完整的 REST API，支援外部系統調用：
- `POST /api/voice/huangrong` - 產生語音並回傳 URL
- `POST /api/voice/huangrong/stream` - 直接返回音訊流

### ChatKit 集成
提供完整的前端集成範例，包含 React 組件、Next.js API Route 等。

## 🧪 開發指引

詳細開發指引請參考專案文件中的開發說明。

## 📝 授權

本專案為開發測試用途。
## 一鍵啟動與驗收

- Windows 一鍵：
  - `powershell -ExecutionPolicy Bypass -File scripts/start-realtime-dev.ps1`
  - 自動建立 `.venv`、安裝 Python 依賴、`npm install` 前端套件，並生成 `.env` / `frontend/.env.local`
  - 預設同時啟動 API（http://localhost:8000）與前端 Dev（http://localhost:5173）
  - 參數：`-SkipTests` 跳過測試、`-SkipStart` 只做環境
- 跨平台：
  - `python scripts/dev_setup.py --start`

環境檢查：`python check_config.py`
全測試：`python -m pytest -q`

## CI/CD Pipeline

- GitHub Actions Workflow：`.github/workflows/ci-cd.yml`
  - PR 與 push 自動執行 `pytest`、`npm run build`
  - `main` branch 透過 Vercel（前端）與 Railway（後端）自動部署
- 必要 GitHub Secrets：
  - `VERCEL_TOKEN`, `VERCEL_PROJECT_ID`, `VERCEL_ORG_ID`
  - `RAILWAY_TOKEN`（必要）與 `RAILWAY_ENVIRONMENT`（可選）
  - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- Feature Flags / Observability：
  - `ENABLE_EMOTION_AI_P1`（開啟 Emotion AI Phase 1 worker）
  - `OBS_SUPABASE_URL`, `OBS_SUPABASE_SERVICE_KEY`, `OBS_METRICS_TABLE`, `OBS_SESSIONS_TABLE`, `OBS_ROLE_SWITCH_TABLE`
  - `GATEWAY_ROLES`（JSON，自訂多角色 Voice ID / 優先權 / 最大連線數）
- 設定檔：
  - `frontend/vercel.json`（Vercel）
  - `railway.toml`（Railway）
  - Telemetry client 會自動偵測上述觀測環境變數，無設定時 fallback 到 console log

## WebSocket 端點（Realtime 骨架）

- 路徑：`/api/realtime/ws`
- 上行：
  - 文本：`"ping"`（回 `pong`）或一般文字（回 echo）
  - 二進制：音訊分片（目前回傳占位 energy 事件）
- 下行事件示例：
```json
{"type":"echo","text":"hello"}
{"type":"energy","value":0.6,"ts":1731000000000}
{"type":"emotion","value":"neutral","intensity":0.5}
```

健康檢查：`GET /healthz`，版本：`GET /version`

### Whisper Realtime（本地推理）

- 依賴：`pip install faster-whisper numpy soundfile`（腳本會自動裝）
- 音訊解碼：優先使用系統 `ffmpeg`；如無則可選安裝 `av`（PyAV）
  - Windows 安裝 ffmpeg：`winget install Gyan.FFmpeg` 或從官網下載並加入 PATH
- 事件：
  - 上行二進制音訊（webm/opus 分片） → 後端轉 16kHz mono wav → STT → 下行
  - 下行示例：`{"type":"transcript","text":"...","is_final":true}`

### ElevenLabs Streaming（TTS over WS）

- 端點：`/api/voice/stream-ws`
- 上行事件：
  - `{"type":"speech","text":"你好","voice_id":"<可選>"}`
  - `{"type":"stop"}`
  - `{"type":"ping"}` → 回 `pong`
- 下行事件：
```json
{"type":"tts_chunk","mime":"audio/mpeg","data":"<base64>"}
{"type":"tts_done"}
{"type":"error","message":"..."}
```
- 前端播放建議：
  - 將 `data` base64 轉為 `Uint8Array`，累積到 `MediaSource` 或以 `AudioContext.decodeAudioData` 解碼後排程播放；或臨時以 Blob URL 逐段播放（實作簡單但延遲略高）。

## 流暢度優化參數（.env 可調）

- STT_THROTTLE_MS（預設 700）：增量 transcript 推送的節流間隔（ms）
- STT_SILENCE_MS（預設 1500）：視為句尾沉默的時間（ms），到達後推送 is_final:true
- STT_ENERGY_MS（預設 120）：energy 事件的節流間隔（ms）
- TTS_CHUNK_BYTES（預設 24576）：單次讀取的 TTS 音訊 bytes（越大事件越少）
- TTS_AGGREGATE（預設 2）：聚合 N 個 chunk 再送出一次，降低事件密度

前端已實作：
- 啟播緩衝：累積 ≥3 塊再播放
- 丟棄策略：queue > 50 時丟最舊 5 塊，避免堆積
- 批次 append：每次最多追加 2 塊，降低 update 次數
