#!/usr/bin/env bash
# Let’s Encrypt 证书续期说明（打印到终端，不执行续期）
cat <<'EOF'
证书有效期约 90 天。建议在宿主机 crontab 增加每月两次的续期任务，例如：

0 3,15 * * * cd /path/to/benchmark/volc-standalone && docker run --rm \
  -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
  -v "$(pwd)/certbot/www:/var/www/certbot" \
  certbot/certbot:latest renew --webroot -w /var/www/certbot \
  && docker compose exec nginx nginx -s reload

说明：
- 将 /path/to/benchmark/volc-standalone 替换为实际解压路径。
- renew 仅在临近过期时才会真正更新；成功后 reload Nginx 加载新证书。
- 签发与续期均需本机 80 端口可被 Let’s Encrypt 访问（HTTP-01）。

EOF
