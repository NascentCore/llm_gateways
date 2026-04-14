# NewAPI / Token 网关现状

**飞书 Wiki**：https://tricorder.feishu.cn/wiki/ArAHwWv7xixTwYk4U91cTs4unld

**更新**：2026-04-14

---

## 时间线

| 时间 | 事项 |
|------|------|
| 2026-03 上旬～中旬 | 做 Docker Compose 部署；群里对齐 OpenRouter、Vertex 测试路径；支付相关官方文档（payment-settings）整理转发，Stripe 字段、易支付前置条件（企业、银行账户）说明。 |
| 2026-03 中旬 | Token 聚合群里同步 Vertex 渠道默认模型列表过时、要更新；Claude Code 走网关：新版本对非标准转发更敏感，经当前 NewAPI 转发可能不可用，后续随版本再验。 |
| 2026-03 中下旬 | 对齐对外 model ID 与渠道上游 model ID；IM 说明当前配置下「同一 Key 按模型绑不同渠道」做不到，替代思路如模型重定向（以当时后台为准）。 |
| 2026-03 中下旬 | GCP Service Account JSON 在自有 NewAPI 上验证可用；配合普通账号、扩展性/模型列表等测试（建号、体验路径）。 |
| 2026-03 下旬 | LiteLLM vs NewAPI 对比素材（半页纸量级）；NewAPI 设置项较多，系统整理尚未落稿。 |
| 2026-03 底 | 补充飞书 Wiki：OpenClaw 对接、Chat 测试交付等；群内同步对外网关验证材料方向。 |
| 2026-04-09 | 于远程主机对 `https://api.mixroute.ai/v1` 完成连通性与高并发阶梯加压验证，结果写入 `docs/newapi-mixroute-validation-*.md`，并在协作群内同步 Git 文档链接。 |

---

## 当前状态

**已阶段性落地**

- 部署：以官方 Docker Compose 为主；Vertex 、openrouter、minimax,moonshoot 渠道自有环境已对接验证。目前服务地址 https://llm.sxwl.ai/ ，部署在字节
- 配置： 以官方操作文档为准，针对特定配置操作如模型价格配置，模型id配置，已验证并文档落实到文档
- 对接：OpenAI 兼容 chat、Anthropic Messages 两路多模型连通性已完成验证，openclaw以及claude code的对接验证。
- 压测：
  - 在google cloud上对接mock llm服务，完成多场景（不同输入输出token）下newapi的吞吐指标。
  - 基于mixroute 已完成一轮大 payload + 阶梯并发脚本压测，产出 RPM/TPM 粗算与延迟分布（**非 SLA**，以报告为准）。
- 飞书已沉淀若干操作/对接类说明；仓库提供可复现命令与脚本。

---

## 飞书文档（操作/交付）

云文档可在知识库内按标题检索；如需固定入口，可在下表自行补充链接列。

| 用途 | 标题 |
|------|------|
| OpenClaw 对接 | OpenClaw 对接 NewAPI 自定义网关服务操作指南 |
| Claude code对接 | claude-code对接 |
| Chat 交付 | NewAPI Chat 接口测试 — 交付文档 |
| 吞吐/说明 | NewAPI 测试吞吐量 |
| 配置 | 大模型 API 聚合平台；为模型配置价格；claude-code对接 |

---

## 仓库里的压测 / 测试 / 报告

仓库：`llm_gateways`，供研发与运维克隆后按各目录 `README` 或验证报告内命令执行。

| 路径 | 说明 |
|------|------|
| `benchmark/` | 端到端压测：Mock + NewAPI Compose + Locust；入口见 `README.md`、`OPERATIONS.md` |
| `benchmark/mock/` | OpenAI 兼容 Mock，可配置延迟与输出规模 |
| `benchmark/newapi/` | NewAPI + PostgreSQL + Redis Compose，用于压测环境起栈 |
| `benchmark/locust/` | 多场景压测，输出 CSV/HTML 报表 |
| `scripts/rpm_until_limit.py` | OpenAI 兼容 chat 并行阶梯加压，输出近似 RPM、延迟分位；适用于真实网关 URL 与大 prompt 场景 |
| `test_chat.py` | 连通性冒烟：OpenAI / Anthropic SDK 双路径 |
| `scripts/newapi_batch_accounts/` | 管理端批量创建用户、额度与 API Key（需管理员权限） |
| `docs/newapi-mixroute-validation-2026-04-09.md` | api.mixroute.ai 技术验证全文 |
| `docs/newapi-mixroute-validation-executive-brief-2026-04-09.md` | 同上，业务简报 |
| `docs/newapi-pricing-and-models.md` | 配额、倍率、渠道模型列表与映射，后台改价/改映射时对照 |

---

## 后续工作

1. Vertex 模型列表维护
2. 在现有文档与 benchmark 基础上，将重复部署步骤脚本化
