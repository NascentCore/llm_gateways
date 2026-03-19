# NewAPI 压测套件

本目录包含三部分：Mock 上游服务、NewAPI 单机部署、Locust 压测客户端，用于在 GCP 三台机器上完成端到端压测。

**操作与验证请直接查看 [OPERATIONS.md](OPERATIONS.md)**，按其中三步执行即可。

## 目录说明

| 目录/文件 | 用途 |
|-----------|------|
| [OPERATIONS.md](OPERATIONS.md) | **操作文档**：三步部署与压测、验证检查清单 |
| [mock/](mock/) | OpenAI 兼容 Mock 服务（FastAPI），可配置输出 token 数；含 Dockerfile 与 deploy.sh |
| [newapi/](newapi/) | NewAPI + PostgreSQL + Redis 的 Docker Compose，含 4 核 8G 资源分配 |
| [locust/](locust/) | Locust 多 case（input/output token）压测，CSV/HTML 分桶报表 |

## 快速链接

- Mock 部署：`mock/deploy.sh`
- NewAPI 部署：`newapi/deploy.sh`
- 压测运行：`locust/README.md` 中的命令与环境变量
