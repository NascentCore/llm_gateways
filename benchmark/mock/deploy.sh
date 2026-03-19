#!/usr/bin/env bash
# Mock 服务部署脚本：构建并运行 Docker 容器（可在 GCE 或本机执行）
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

IMAGE_NAME="${IMAGE_NAME:-llm-gateways-mock}"
CONTAINER_NAME="${CONTAINER_NAME:-mock-openai}"
PORT="${PORT:-8000}"
# 默认输出 token 数，可通过环境变量覆盖
MOCK_OUTPUT_TOKENS="${MOCK_OUTPUT_TOKENS:-64}"
# 单次 max_tokens 上限（大 output 压测时提高，如 500000）
MOCK_MAX_COMPLETION_TOKENS="${MOCK_MAX_COMPLETION_TOKENS:-262144}"

# 默认使用 Docker Hub；若拉取失败请在 Docker 里配置镜像加速后重试，或设置 BASE_IMAGE 为你可用的镜像
BASE_IMAGE="${BASE_IMAGE:-python:3.12-slim}"
echo "Building image: $IMAGE_NAME (base: $BASE_IMAGE)"
docker build --build-arg BASE_IMAGE="$BASE_IMAGE" -t "$IMAGE_NAME" .

echo "Stopping existing container (if any)..."
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

echo "Starting container: $CONTAINER_NAME on port $PORT"
docker run -d --name "$CONTAINER_NAME" \
  -p "${PORT}:8000" \
  -e MOCK_OUTPUT_TOKENS="$MOCK_OUTPUT_TOKENS" \
  -e MOCK_MAX_COMPLETION_TOKENS="$MOCK_MAX_COMPLETION_TOKENS" \
  --restart unless-stopped \
  "$IMAGE_NAME"

echo "Mock service is running at http://localhost:$PORT"
echo "  Health: http://localhost:$PORT/health"
echo "  Chat:   POST http://localhost:$PORT/v1/chat/completions"
