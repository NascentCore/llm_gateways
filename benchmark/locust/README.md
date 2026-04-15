# Locust 压测 NewAPI

内置 **6 组** input/output token case（权重相同），报表中按名称分桶，例如 `/v1/chat/completions in=2000 out=100`。各组为：

| input≈ | output (max_tokens) |
|--------|----------------------|
| 2000 | 100 |
| 20000 | 1000 |
| 200000 | 50000 |
| 100 | 2000 |
| 1000 | 20000 |
| 50000 | 200000 |

Mock 端需将 `MOCK_MAX_COMPLETION_TOKENS` 设得 ≥ 最大 output（默认 262144 即可）。NewAPI/反向代理需允许大请求体与大响应、足够读超时。

## 安装

```bash
pip install -r requirements.txt
# 或 uv: uv pip install -r requirements.txt
```

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| NEWAPI_BASE_URL | NewAPI 根地址（不含 /v1） | http://localhost:3000 |
| NEWAPI_API_KEY | NewAPI 令牌 | 必填 |
| NEWAPI_MODEL | 请求使用的模型名（与渠道一致） | mock-model |
| LOCUST_REQUEST_TIMEOUT | 大 case 使用的请求超时（秒）；小 case 取 min(本值, 120) | 300 |

## 运行

**无 UI（推荐用于脚本/CI）**

```bash
export NEWAPI_BASE_URL=http://NEWAPI_IP:3000
export NEWAPI_API_KEY=sk-xxx

locust -f locustfile.py --headless \
  -u 50 -r 10 -t 300s \
  --host="$NEWAPI_BASE_URL" \
  --csv=report --html=report.html
```

- `-u 50`：并发用户数 50  
- `-r 10`：每秒启动 10 个用户  
- `-t 300s`：运行 300 秒  
- `--host`：Locust 2.x 必填（与 `NEWAPI_BASE_URL` 一致）  
- `--csv=report`：生成 report_stats.csv、report_failures.csv 等  
- `--html=report.html`：生成 HTML 报告  

**有 Web UI**

```bash
locust -f locustfile.py --host=http://NEWAPI_IP:3000
# 浏览器打开 http://localhost:8089 设置用户数与时长后启动
```

## 报告

- `*_stats.csv`：请求数、RPS、延迟分位、失败数（按各 in/out case 分行）  
- `*_failures.csv`：失败请求明细  
- `report.html`：可视化报告  
- **`locust_last_token_metrics.json`**（无 UI / headless 结束时由 `locustfile.py` 写入）：整段压测的 **RPM**（全部请求/分钟）与 **TPM**（按响应 `usage` 累加 `total_tokens` / 分钟，并拆 prompt、completion）。终端结束时会打印同内容摘要。仅适合**单机**压测；分布式多 worker 时 token 未汇总。

建议每轮压测使用不同前缀，例如：`--csv=run_$(date +%Y%m%d_%H%M%S)`。

### 终端摘要（`summarize_run.py`）

跑完后在 `locust` 目录执行（默认取当前目录**最新**的 `*_stats.csv`，排除 `*_stats_history.csv`）：

```bash
python3 summarize_run.py
# 或指定文件，并打印失败明细
python3 summarize_run.py report_stats.csv --failures
```

脚本仅依赖 Python 标准库。
