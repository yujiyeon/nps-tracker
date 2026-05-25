#!/bin/bash
# 매일 07:00 KST launchd에 의해 실행되는 수집 스크립트
# 서버에서는 이 스크립트 대신 APScheduler(daily_runner.py)가 직접 담당

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$SCRIPT_DIR/logs/launchd_$(date +%Y-%m-%d).log"

mkdir -p "$SCRIPT_DIR/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 수집 시작" >> "$LOG_FILE"

# .env 로드 (launchd는 쉘 환경변수를 상속하지 않으므로 직접 로드)
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

cd "$SCRIPT_DIR" && \
  .venv/bin/python -m scrapers.daily_runner --now >> "$LOG_FILE" 2>&1

STATUS=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 수집 종료 (exit: $STATUS)" >> "$LOG_FILE"
exit $STATUS
