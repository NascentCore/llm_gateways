# Vertex AI PT vs PayGo 成本对比计算器

浏览器本地运行的静态页面：固定 **模型预设**、**PT 合约与 GSU**、**每月用量**（或按请求推算），计算对比窗口内的 **PT 固定成本** 与 **Standard PayGo 按量成本**，并显示平均 burndown/s 与容量利用率。

## 运行方式

- **直接打开**：双击或用浏览器打开 `index.html`（部分浏览器对 `file://` 加载本地 JS 较严，若脚本不执行请用下面方式）。
- **本地 HTTP（推荐，需 Node）**：

```bash
cd tools/pt-paygo-calculator
npx -y serve . -p 5173
```

浏览器访问终端里提示的地址（一般为 `http://localhost:5173`）。

## 计算说明

- **PayGo**：`(input/1e6)*单价 + (output_text/1e6)*单价 + (output_image/1e6)*单价`，用量按「每月」填，再按 **对比窗口天数 / 30** 缩放。
- **PT**：按所选合约折算到窗口内成本  
  - 周约：`GSU × $1,200 × (天数/7)`  
  - 月约 / 三月约 / 年约：`GSU × 月价 × (天数/30)`  
  其中三月约与年约的「月价」分别为 $2,400、$2,000（与官方定价表一致）。
- **利用率**：在「按请求」模式下，用单次平均 token 算 `burndown/请求`，乘以窗口内请求数，再除以 `窗口秒数` 得平均 burndown/s，与 `GSU × throughput/GSU` 比较。超过 100% 时仅提示可能 spillover；**PayGo 一行仍为全量 token 的按量估算**，未做 PT+溢出双计拆分。
- **PT 摊销 $/M**：将窗口内 PT 总成本按各向 token 的 **burndown 贡献占比** 分摊，再除以对应百万 token，与仓库 `REFERENCES.md` 中文本 1:1 满负载示例口径一致。

## 数据来源与免责

- [Vertex AI 定价 — Provisioned Throughput](https://cloud.google.com/vertex-ai/generative-ai/pricing#provisioned-throughput)
- [Supported models / burndown rates](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/provisioned-throughput/supported-models)

Google 可能调整价格与 burndown，请以官方文档为准。本工具仅供估算，不构成报价或合同依据。

## 仓库内文档

项目根目录 [REFERENCES.md](../../REFERENCES.md) 中有 PT 要点与 Nano Banana 2 示例数字，可与本计算器交叉核对。
