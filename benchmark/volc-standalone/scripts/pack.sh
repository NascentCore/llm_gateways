#!/usr/bin/env bash
# 在仓库内从 benchmark/ 目录执行，生成可上传火山 ECS 的 tar.gz
set -euo pipefail
BENCH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$BENCH"

OUT="volc-benchmark-$(date +%Y%m%d_%H%M%S).tar.gz"

tar czvf "$OUT" \
  --exclude='volc-standalone/.env' \
  --exclude='volc-standalone/data' \
  --exclude='volc-standalone/logs' \
  --exclude='volc-standalone/nginx/active.conf' \
  --exclude='volc-standalone/certbot/conf/archive' \
  --exclude='volc-standalone/certbot/conf/live' \
  --exclude='volc-standalone/certbot/conf/renewal' \
  --exclude='volc-standalone/certbot/conf/*.pem' \
  --exclude='__pycache__' \
  --exclude='.DS_Store' \
  VOLC_STANDALONE.md mock locust volc-standalone

echo ""
echo "已生成: $BENCH/$OUT"
echo "上传到 ECS 后解压，进入 volc-standalone 目录按 VOLC_STANDALONE.md 操作。"
