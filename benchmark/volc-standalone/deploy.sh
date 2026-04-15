#!/usr/bin/env bash
# 生成初始 Nginx 配置（若缺失）并启动全栈
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -f nginx/active.conf ]]; then
  ./scripts/bootstrap.sh
fi

docker compose up -d --build
