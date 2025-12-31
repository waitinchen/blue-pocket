# 簡化的 Dockerfile - 只構建後端 API
# 跳過前端構建，因為情報自動化模組只需要後端

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 安裝依賴
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程序代碼
COPY main.py ./
COPY src/ ./src/ 2>/dev/null || true

# 創建日誌目錄
RUN mkdir -p logs

# 暴露端口
EXPOSE 8080

# 啟動命令（Railway 會使用 Settings 中配置的 Start Command）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
