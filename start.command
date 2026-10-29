#!/usr/bin/env bash
# Finder entry point for macOS. Keep the terminal open if setup needs attention.
set -o pipefail
ROOT=$(cd -- "$(dirname -- "$0")" && pwd)
LOG_FILE="$ROOT/.docker-launch.log"
"$ROOT/scripts/deploy.sh" up 2>&1 | tee "$LOG_FILE"
result=${PIPESTATUS[0]}
if [ "$result" -eq 0 ]; then
  url=$("$ROOT/scripts/deploy.sh" url) && open "$url" 2>> "$LOG_FILE"
fi
printf '\n启动日志：%s\n' "$LOG_FILE"
if [ -t 0 ]; then
  printf '\n按 Enter 关闭此窗口（运行中的容器会继续运行）……'
  read -r _
fi
exit "$result"
