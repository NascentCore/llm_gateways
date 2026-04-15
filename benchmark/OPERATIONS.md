# NewAPI 压测操作文档

本文档用于在 GCP 三台机器上完成：Mock 服务部署、NewAPI 部署、Locust 压测与结果验证。

---

## 架构与机器角色

| 机器 | 角色 | 建议配置 | 说明 |
|------|------|----------|------|
| 机器 1 | NewAPI + PostgreSQL + Redis | 4 核 8G | 运行 `benchmark/newapi/` 的 Docker Compose |
| 机器 2 | Mock 上游服务 | 2 核 4G 即可 | 运行 `benchmark/mock/` 的 Docker |
| 机器 3 | 压测客户端 | 2 核 4G 即可 | 运行 Locust（`benchmark/locust/`） |

网络：三台机器需能互通（同 VPC 或放行相应端口）。机器 1 需能访问机器 2 的 Mock 端口；机器 3 需能访问机器 1 的 3000 端口。

---

## 第一步：部署 Mock 服务（机器 2）

1. 将本仓库中的 `benchmark/mock/` 拷贝到机器 2（或在该机器上 clone 仓库后进入 `benchmark/mock`）。

2. 构建并运行：

   ```bash
   cd benchmark/mock
   chmod +x deploy.sh
   # 可选：指定端口、默认输出 token、单次 max_tokens 上限（多 case 大 output 压测时建议 ≥262144）
   # export MOCK_OUTPUT_TOKENS=128
   # export MOCK_MAX_COMPLETION_TOKENS=262144
   # export PORT=8000
   ./deploy.sh
   ```

3. 验证：

   ```bash
   curl http://localhost:8000/health
   # 应返回 {"status":"ok"}

   curl -X POST http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"mock","messages":[{"role":"user","content":"hi"}],"max_tokens":8}'
   # 应返回 OpenAI 格式的 JSON，含 choices[0].message.content 和 usage
   ```

4. 记录机器 2 的 **内网 IP**（或对外暴露的 IP 与端口），供 NewAPI 配置渠道时使用，例如：`http://<MOCK_IP>:8000`。

---

## 第一步（备选）：使用 Cloud Run 部署 Mock 服务

若不使用 GCE 虚拟机跑 Mock，可将 Mock 部署到 **Cloud Run**，由 NewAPI（机器 1）通过 Cloud Run 的 URL 访问。若需仅在 VPC 内网访问，使用 `--ingress=internal`。

**前置条件**：已安装 `gcloud`、已登录并设置默认项目（`gcloud config set project PROJECT_ID`）；已启用 Cloud Run API 与 Artifact Registry API。

1. **设置区域变量**：`REGION` 必须为**区域**（如 `us-central1`、`asia-east1`），不能是可用区（如 `us-central1-a`）。Artifact Registry 与 Cloud Run 均按区域部署。

   ```bash
   export PROJECT_ID=$(gcloud config get-value project)
   export REGION=us-central1
   ```

2. **配置 Docker 认证**（首次推送前必须执行，否则会报 Unauthenticated）：

   ```bash
   gcloud auth configure-docker ${REGION}-docker.pkg.dev
   ```
   按提示确认后，`docker push` 才能推送到该项目的 Artifact Registry。

3. **创建 Artifact Registry 仓库**（若尚未创建）：

   ```bash
   gcloud artifacts repositories create mock-repo \
     --repository-format=docker \
     --location=${REGION} \
     --description="Mock OpenAI image"
   ```
   若提示已存在，可用 `gcloud artifacts repositories list` 确认仓库及其 `location` 与上面 `REGION` 一致。

4. **构建并推送镜像**（在本地或 Cloud Shell，且本机可访问 `benchmark/mock` 目录）：

   **方式 A：本地构建（推荐在 x86 机器或指定 amd64 平台）**  
   Cloud Run 运行在 **linux/amd64**。若在 **Apple Silicon (M1/M2/M3)** 上构建，必须加 `--platform linux/amd64`，否则会报 `exec format error` 导致容器无法启动。

   ```bash
   cd benchmark/mock
   docker build --platform linux/amd64 -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/mock-repo/mock:latest .
   docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/mock-repo/mock:latest
   ```

   **方式 B：使用 Cloud Build 构建**（无需本地 Docker Hub、且默认 amd64，推荐）：  
   ```bash
   cd benchmark/mock
   gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/mock-repo/mock:latest .
   ```
   构建在 GCP 上执行，自动为 amd64，且不依赖本机拉取基础镜像。

5. **部署到 Cloud Run**：  
   Cloud Run 会注入环境变量 **PORT=8080**，容器必须监听该端口（本仓库 Mock 的 Dockerfile 已支持通过 `PORT` 监听）。

   **公网可访问（默认）：**
   ```bash
   gcloud run deploy mock \
     --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/mock-repo/mock:latest \
     --region=${REGION} \
     --platform=managed \
     --allow-unauthenticated \
     --set-env-vars="MOCK_OUTPUT_TOKENS=64,MOCK_MAX_COMPLETION_TOKENS=262144"
   ```

   **仅 VPC 内网访问（推荐用于压测）：** 使用 `--ingress=internal`，则仅同一 VPC 内（如机器 1 的 GCE）可访问，公网无法访问。
   ```bash
   gcloud run deploy mock \
     --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/mock-repo/mock:latest \
     --region=${REGION} \
     --platform=managed \
     --ingress=internal \
     --allow-unauthenticated \
     --set-env-vars="MOCK_OUTPUT_TOKENS=64,MOCK_MAX_COMPLETION_TOKENS=262144"
   ```
   确保机器 1（NewAPI）所在 VPC 已开启 **Private Google Access**（子网 → 编辑 → Private Google access 开启）。

6. **获取 Mock 地址**：部署完成后，控制台会输出 **Service URL**（如 `https://mock-xxx-REGION.run.app`）。NewAPI 渠道的「基础 URL」填该地址（不要带 `/v1`）。

7. **验证**（在能访问该服务的环境执行，若为 internal 则需在 VPC 内 GCE 上执行）：
   ```bash
   curl https://mock-xxx-REGION.run.app/health
   curl -X POST https://mock-xxx-REGION.run.app/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"mock","messages":[{"role":"user","content":"hi"}],"max_tokens":8}'
   ```

采用 Cloud Run 部署 Mock 时，可不再使用「机器 2」；在 **第二步** 中 NewAPI 渠道的基础 URL 填上述 Cloud Run Service URL 即可。

---

## 第二步：部署 NewAPI（机器 1）

1. 将本仓库中的 `benchmark/newapi/` 拷贝到机器 1，进入目录：

   ```bash
   cd benchmark/newapi
   ```

2. 可选：修改默认密码。复制环境变量示例并编辑：

   ```bash
   cp .env.example .env
   # 编辑 .env，修改 POSTGRES_PASSWORD（生产环境务必修改）
   ```

3. 启动栈：

   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

4. 在 NewAPI 中配置渠道与令牌：

   - 浏览器访问 `http://<机器1_IP>:3000`，使用初始账号登录（默认 root / 123456，首次登录后请修改密码）。
   - **渠道**：新增渠道，类型选择 **OpenAI 兼容**（或 Custom），基础 URL 填 Mock 地址：`http://<MOCK_IP>:8000`（虚拟机部署）或 Cloud Run 的 Service URL（如 `https://mock-xxx-REGION.run.app`，不要带 `/v1`），API Key 可填任意占位（如 `mock`），模型填写与压测一致的名称，例如 `mock-model`，保存。
   - **令牌**：在「令牌」中新增一个 Token，记下该 **API Key**（如 `sk-xxx`），供机器 3 压测使用。

5. 验证：

   ```bash
   curl -X POST http://localhost:3000/v1/chat/completions \
     -H "Authorization: Bearer sk-你的令牌" \
     -H "Content-Type: application/json" \
     -d '{"model":"mock-model","messages":[{"role":"user","content":"hi"}],"max_tokens":8}'
   # 应返回与直接调 Mock 类似的 JSON，说明网关转发正常
   ```

---

## 第三步：压测（机器 3）

1. 在机器 3 上进入 Locust 目录并安装依赖：

   ```bash
   cd benchmark/locust
   pip install -r requirements.txt
   ```

2. 设置环境变量（替换为实际值）：

   ```bash
   export NEWAPI_BASE_URL=http://<机器1_IP>:3000
   export NEWAPI_API_KEY=sk-你的令牌
   export NEWAPI_MODEL=mock-model
   # 可选：大 case 请求超时（秒），默认 300
   # export LOCUST_REQUEST_TIMEOUT=300
   ```

3. 运行无 UI 压测（示例：50 用户、每秒 10 用户启动、持续 300 秒，并输出 CSV 与 HTML）：

   ```bash
   locust -f locustfile.py --headless -u 50 -r 10 -t 300s \
     --host="$NEWAPI_BASE_URL" \
     --csv=report --html=report.html
   ```

4. 查看结果：

   - 控制台会打印汇总的 RPS、延迟、失败数等。
   - 终端摘要：`python3 summarize_run.py` 或 `python3 summarize_run.py report_stats.csv --failures`（若存在 `locust_last_token_metrics.json`，会显示 **RPM / TPM**）。
   - 当前目录会生成：
     - `report_stats.csv`：各请求类型的统计（按 `/v1/chat/completions in=… out=…` 分桶，便于对比不同 input/output 下的吞吐）。
     - `report_failures.csv`：失败请求明细（若有）。
     - `report.html`：可在浏览器中打开查看图表与统计。

5. 可选：使用 Web UI 手动调节并发与时长：

   ```bash
   locust -f locustfile.py --host=http://<机器1_IP>:3000
   # 浏览器打开 http://localhost:8089，输入用户数、每秒启动数、运行时长后点击 Start
   ```

---

## 多 input/output token case 压测说明

- Locust 内置 6 组 `(prompt 约等于 input_tokens, max_tokens)`，权重相同，统计按请求 **name** 拆分。
- **Mock**：部署时设置 `MOCK_MAX_COMPLETION_TOKENS` ≥ 本批最大 output（如 `200000`）；默认 `262144` 已覆盖内置 case。每个 case 的实际输出由请求里的 `max_tokens` 决定，**无需**按 case 改 Mock 环境或重启。
- **NewAPI / 反向代理**：大 body（约 200k input）与大响应（约 200k output）需放宽 **请求体大小**、**读超时**；Locust 对大 case 使用较长 `timeout`，若网关先断开仍会失败，需与 `LOCUST_REQUEST_TIMEOUT`（见 `benchmark/locust/README.md`）一并核对。

---

## 验证检查清单

- [ ] **Mock（机器 2 或 Cloud Run）**：`GET /health` 返回 200；`POST /v1/chat/completions` 返回含 `choices` 与 `usage` 的 JSON。
- [ ] **NewAPI（机器 1）**：`/api/status` 可访问；使用 Token 调用 `POST /v1/chat/completions` 返回正常内容。
- [ ] **压测（机器 3）**：Locust 无 UI 运行结束无报错；`report_stats.csv` 中有多条 `/v1/chat/completions in=… out=…`；失败数为 0 或可接受；`report.html` 中延迟与 RPS 符合预期。

---

## 目录结构速览

```
benchmark/
├── OPERATIONS.md          # 本文档
├── mock/                  # 第一步：Mock 服务
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── deploy.sh
├── newapi/                # 第二步：NewAPI 部署
│   ├── docker-compose.yml
│   ├── .env.example
│   └── deploy.sh
└── locust/                # 第三步：压测客户端
    ├── locustfile.py
    ├── requirements.txt
    ├── config.example.env
    └── README.md
```

---

## 常见问题

- **压测大量失败**：检查机器 3 到机器 1 的 3000 端口是否可达；检查 NewAPI 中 Token 是否有效、渠道是否启用、Mock 地址是否可从机器 1 访问。
- **NewAPI 无法访问 Mock**：在机器 1 上执行 `curl http://<MOCK_IP>:8000/health`，确认网络与安全组/防火墙放行。
- **需调整 Mock 默认输出或未传 max_tokens 时的行为**：设置 `MOCK_OUTPUT_TOKENS`。多 case 压测下各请求自带 `max_tokens`，与 `MOCK_MAX_COMPLETION_TOKENS`（上限）配合即可。
- **大 output 返回被截断或 4xx**：提高 Mock 的 `MOCK_MAX_COMPLETION_TOKENS`，并检查网关 body/超时限制。
- **Cloud Run Mock 仅内网（ingress=internal）时 NewAPI 无法访问**：确认机器 1 所在 VPC 与 Cloud Run 同项目，且子网已开启 Private Google Access；从机器 1 上 `curl https://<Cloud-Run-URL>/health` 测试。
- **Cloud Run 报 "exec format error" 或 "failed to load /usr/bin/sh"**：镜像架构与 Cloud Run（linux/amd64）不一致。在 Apple Silicon Mac 上构建时请加 `--platform linux/amd64`，或改用 `gcloud builds submit` 在 GCP 上构建。
- **docker push 报 "Repository not found"**：先用 `gcloud artifacts repositories create mock-repo --repository-format=docker --location=REGION` 创建仓库，且 REGION 为区域（如 `us-central1`），不能为可用区（如 `us-central1-a`）。
- **docker push 报 "Unauthenticated request"**：执行 `gcloud auth configure-docker REGION-docker.pkg.dev` 配置 Docker 对该 registry 的认证后再推送。
