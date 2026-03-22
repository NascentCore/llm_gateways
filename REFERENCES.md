# 参考资料

[如何应对 Vertex AI 429（资源不足）错误](https://cloud.google.com/blog/products/ai-machine-learning/reduce-429-errors-on-vertex-ai)
[429 错误](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/provisioned-throughput/error-code-429)：

1. Pay as you go 层级，资源耗尽
2. Provisioned Throughput 层级：超出使用上限

## Vertex AI Provisioned Throughput 要点

- [Provisioned Throughput 概览](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/provisioned-throughput/overview)
- [消费选项对比](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/deploy/consumption-options)
- [GSU 与 burndown 计费](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/provisioned-throughput/measure-provisioned-throughput)
- [PT 定价](https://cloud.google.com/vertex-ai/generative-ai/pricing#provisioned-throughput)

### 核心结论（基于官方文档）

1. **PT 需高利用率才划算**：PT 为固定月费/周费（按 GSU），未用容量**不累积、不结转**。非 24 小时使用会导致有效单价升高。文档建议用 right-sizing 覆盖基线流量，超出的用 PayGo。
2. **配额提升**：复杂需求或需要更高 QPM（如 >30k）时，可通过 [Quota 申请](https://cloud.google.com/docs/quotas/help/request_increase) 或 [联系 account representative](https://cloud.google.com/contact) 提升层级。

### Nano Banana 2 (Gemini 3.1 Flash Image) PT vs PayGo 成本对比

**模型参数：**
- PT 吞吐：2,015 burndown tokens/秒/GSU
- Burndown：input text/image = 1，output text = 6，output image = 120
- PT 价格：1 年 $2,000/GSU/月，1 月 $2,700/GSU/月

**PayGo Standard ($/1M tokens)：**

| 类型 | 价格 |
|------|------|
| Input (text, image) | $0.50 |
| Output text | $3.00 |
| Output image | $60.00 |

**PT 等效 $/1M tokens（100% 利用率，文本 1:1 场景）：**

| 类型 | PT 1 年 | PT 1 月 | PayGo |
|------|---------|---------|-------|
| Input | $0.38 (~省 24%) | $0.51 (~贵 2%) | $0.50 |
| Output text | $2.30 (~省 23%) | $3.10 (~贵 3%) | $3.00 |

**结论：**
- 1 年 PT 在满负载下比 PayGo 便宜约 23–24%
- 1 月 PT 基本无成本优势
- PT 仅在高利用率下划算；利用率低时有效单价上升
