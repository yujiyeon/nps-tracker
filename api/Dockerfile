FROM python:3.11-slim

WORKDIR /app

# non-root 사용자
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 appuser

# 의존성 레이어 (소스보다 먼저 복사 → 캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appgroup . .

USER appuser
EXPOSE 8000
# Railway는 $PORT를 주입함 — 없으면 8000 기본값
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
