# 若拉取失败 (connection reset / failed to fetch token)，可使用镜像源：
#   docker build --build-arg BASE_IMAGE=registry.cn-hangzhou.aliyuncs.com/library/python:3.12-slim -t llm-gateways-mock .
# 或配置 Docker 使用镜像加速后直接 ./deploy.sh
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .

ENV MOCK_OUTPUT_TOKENS=64
ENV MOCK_MAX_COMPLETION_TOKENS=262144
ENV PORT=8000
EXPOSE 8000
# Cloud Run 会注入 PORT；本地不设时默认 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
