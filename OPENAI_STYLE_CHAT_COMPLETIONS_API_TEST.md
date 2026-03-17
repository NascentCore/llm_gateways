# Chat 接口测试 — 交付文档

## 1. 概述

本交付包含用于测试 **LLM API 网关** Chat 接口（OpenAI 兼容 `/v1/chat/completions`）的脚本与使用说明。通过 OpenAI 官方 Python 客户端发起请求，可指定网关地址、API Key 及待测模型列表。

- **测试脚本**：`test_chat.py`
- **运行方式**：使用系统 Python 执行（`python test_chat.py`）
- **API key**：将提供给用户的 API Key 以文本文件 api_key.txt

---

## 2. 环境要求

- **Python**：3.12 或以上
- **依赖**：`openai>=1.0.0`

安装依赖（任选其一）：

```bash
pip install openai
```

---

## 3. 支持的模型列表

以下模型已纳入测试范围，模型 ID 与 渠道配置一致，根据测试场景，目前的模型基本都是各个模型的高性价比主力版本。
既不是最便宜的、也不是最强大的：

| 序号 | 模型 ID                                 |
| ---- | --------------------------------------- |
| 1    | `google/gemini-3-pro-preview`           |
| 2    | `google/gemini-3-flash-preview`         |
| 3    | `anthropic/claude-opus-4.5`             |
| 4    | `openai/gpt-5.2`                        |
| 5    | `x-ai/grok-4`                           |
| 6    | `moonshotai/kimi-k2.5`                  |
| 7    | `minimax/minimax-m2.5`                  |
| 8    | `bytedance/doubao-seed-2-0-mini-260215` |
| 9    | `z-ai/glm-5`                            |

---

## 4. 配置说明

- **Base URL**： 如：`https://35.202.11.188/v1`。
- **API Key**：从环境变量 `OPENAI_API_KEY` 读取，也可通过参数 `--api-key` 传入。

---

## 5. 运行命令

```bash
export OPENAPI_BASE_URL="https://35.202.11.188/v1"
export OPENAPI_API_KEY="你的密钥"

python test_chat.py  \
  -m google/gemini-3-pro-preview \
  -m google/gemini-3-flash-preview \
  -m anthropic/claude-opus-4.5 \
  -m openai/gpt-5.2 \
  -m x-ai/grok-4 \
  -m moonshotai/kimi-k2.5 \
  -m minimax/minimax-m2.5 \
  -m bytedance/doubao-seed-2-0-mini-260215 \
  -m z-ai/glm-5
```

---

## 6. 输出与退出码

- 每个模型一行：`[模型 ID] OK (耗时): 内容摘要` 或 `[模型 ID] FAIL: 错误信息`
- 最后一行：`通过数/总数`，以及 `Exit 0`（全部通过）或 `Exit 1`（存在失败）
- 脚本退出码：全部通过为 0，否则为 1，便于 CI 或脚本串联

---
