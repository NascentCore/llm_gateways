#!/usr/bin/env bash
# 准备目录、.env、初始 HTTP Nginx 配置（用于签发 Let’s Encrypt 前）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "请先安装 Docker 与 docker compose 插件。"
  echo "Ubuntu 示例: https://docs.docker.com/engine/install/ubuntu/"
  exit 1
fi

if [[ ! -f .env ]]; then
  cp -n .env.example .env
  echo "已创建 .env，请编辑 DOMAIN、LETSENCRYPT_EMAIL、POSTGRES_PASSWORD 后重新执行。"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -z "${DOMAIN:-}" || "${DOMAIN}" == "api.example.com" ]]; then
  echo "请在 .env 中将 DOMAIN 改为你在 Namecheap 配置的 A 记录主机名（勿含 https://）。"
  exit 1
fi

mkdir -p data logs certbot/www certbot/conf nginx

if [[ ! -f nginx/active.conf ]]; then
  if ! command -v envsubst >/dev/null 2>&1; then
    echo "未找到 envsubst。Ubuntu: sudo apt-get install -y gettext-base"
    exit 1
  fi
  export DOMAIN
  envsubst '${DOMAIN}' < nginx/http-only.conf.template > nginx/active.conf
  echo "已生成 nginx/active.conf（HTTP + ACME webroot）。"
else
  echo "nginx/active.conf 已存在，跳过生成（避免覆盖 HTTPS 配置）。"
fi

echo ""
echo "下一步:"
echo "  1) 火山安全组放行 TCP 22 / 80 / 443；Namecheap A 记录 ${DOMAIN} -> 本机公网 IP"
echo "  2) 在本目录执行: docker compose up -d --build   （或 ./deploy.sh）"
echo "  3) 证书: ./scripts/issue-cert.sh"
echo ""
