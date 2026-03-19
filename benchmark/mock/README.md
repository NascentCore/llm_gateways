# Mock OpenAI Chat 服务

OpenAI 兼容的 Chat Completions 模拟服务，用于压测 NewAPI 上游。

## 部署

```bash
./deploy.sh
```

可选环境变量：`PORT`、`MOCK_OUTPUT_TOKENS`、`MOCK_MAX_COMPLETION_TOKENS`（单次请求 `max_tokens` 上限，默认 `262144`，需更大 output 时调大）、`IMAGE_NAME`、`CONTAINER_NAME`。

## Docker Hub 拉取失败时

若出现 `failed to fetch anonymous token`、`connection reset by peer` 或 `pull access denied`，多为网络或镜像源不可用，建议：

**配置 Docker 镜像加速（推荐）**

- **OrbStack**：编辑 `~/.orbstack/config/docker.json`，加入或合并 `registry-mirrors` 后重启 OrbStack，例如：
  ```json
  {
    "registry-mirrors": [
      "https://dockerproxy.com",
      "https://docker.mirrors.ustc.edu.cn"
    ]
  }
  ```
- **Docker Desktop**：Settings → Docker Engine → 在 JSON 中增加 `"registry-mirrors": ["https://镜像地址"]`，Apply & Restart。
- 配置完成后执行 `docker info` 可确认 Registry Mirrors 已生效，再执行 `./deploy.sh`。

**或指定可用的基础镜像**

若你有一个可拉取的 Python 镜像（例如自建仓库或其它镜像源），可覆盖默认基础镜像再构建：

```bash
BASE_IMAGE=你的镜像地址/python:3.12-slim ./deploy.sh
```

## 验证

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mock","messages":[{"role":"user","content":"hi"}],"max_tokens":8}'
```
