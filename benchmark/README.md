# NewAPI 压测套件

本目录包含：Mock 上游、NewAPI（Docker Compose）、Locust 压测客户端。可按场景选择部署方式：

| 场景 | 文档 |
|------|------|
| **火山引擎单机 4c8g**（NewAPI + Mock + Nginx + HTTPS + 同机 Locust） | **[VOLC_STANDALONE.md](VOLC_STANDALONE.md)** |
| **GCP 三台机器**（Mock / NewAPI / Locust 分机） | [OPERATIONS.md](OPERATIONS.md) |

## 目录说明

| 目录/文件 | 用途 |
|-----------|------|
| [VOLC_STANDALONE.md](VOLC_STANDALONE.md) | **火山单机操作文档**：Namecheap、Let’s Encrypt、合并 Compose、压测与检查清单 |
| [volc-standalone/](volc-standalone/) | 单机合并栈（`docker-compose.yml`、Nginx 模板、`scripts/pack.sh` 等） |
| [OPERATIONS.md](OPERATIONS.md) | **GCP 三机操作文档**：分步部署与 Cloud Run 备选 |
| [mock/](mock/) | OpenAI 兼容 Mock（FastAPI）；含 Dockerfile 与 `deploy.sh` |
| [newapi/](newapi/) | 仅 NewAPI + PostgreSQL + Redis（4c8g 资源建议）；不含 Nginx/Mock |
| [locust/](locust/) | Locust 多 case 压测，CSV/HTML 分桶报表 |

## 快速链接

- 打物料包（上传 ECS）：`volc-standalone/scripts/pack.sh`（在 `benchmark/` 下执行）
- Mock 单独部署：`mock/deploy.sh`
- NewAPI 单独部署：`newapi/deploy.sh`
- 压测命令与环境变量：`locust/README.md`
