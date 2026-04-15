#!/usr/bin/env bash
# 使用 webroot 模式签发 Let’s Encrypt，并切换 Nginx 为 HTTPS 配置
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "缺少 .env，请先复制 .env.example 并填写。"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

: "${DOMAIN:?请在 .env 中设置 DOMAIN}"
: "${LETSENCRYPT_EMAIL:?请在 .env 中设置 LETSENCRYPT_EMAIL}"

if ! docker ps --filter "name=^benchmark-nginx$" --filter "status=running" -q | grep -q .; then
  echo "Nginx 未运行。请先执行: docker compose up -d"
  exit 1
fi

mkdir -p certbot/www certbot/conf

docker run --rm \
  -v "$ROOT/certbot/conf:/etc/letsencrypt" \
  -v "$ROOT/certbot/www:/var/www/certbot" \
  certbot/certbot:latest certonly \
  --webroot -w /var/www/certbot \
  -d "$DOMAIN" \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos \
  --non-interactive

if ! command -v envsubst >/dev/null 2>&1; then
  echo "未找到 envsubst。Ubuntu: sudo apt-get install -y gettext-base"
  exit 1
fi

export DOMAIN
envsubst '${DOMAIN}' < nginx/https.conf.template > nginx/active.conf

docker compose exec nginx nginx -s reload

echo ""
echo "HTTPS 已启用: https://${DOMAIN}"
echo "续期说明见 scripts/renew-note.sh"
echo ""
