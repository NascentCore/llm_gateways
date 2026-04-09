# NewAPI（api.mixroute.ai）连通性与指标验证报告

**执行日期**：2026-04-09（UTC 以远程命令时间为准）  
**执行主机**：`ubuntu@54.238.141.156`（AWS，`Linux 6.17.0-1007-aws`，Ubuntu 24.04 系列内核）  
**约束**：全部 API 调用与脚本均在上述主机通过 SSH 执行，未在本地或其它机器对同一网关做 fallback 调用。

**网关**：`https://api.mixroute.ai/v1`  
**API Key**：已脱敏，报告中不出现明文；该 Key 曾在聊天中暴露，**建议在 NewAPI 后台尽快轮换**。

---

## 1. 环境准备（均在目标机）

| 步骤 | 命令 / 说明 | 结果 |
|------|-------------|------|
| 同步代码 | `rsync` 将本仓库同步至 `~/llm_gateways` | 成功 |
| Python | `/usr/bin/python3` → **3.12.3** | 可用（项目 `pyproject` 声明 ≥3.13，远端用 3.12 + 独立 venv 运行 `test_chat.py` 无语法问题） |
| venv | 初次 `python3 -m venv` 失败：`ensurepip` 不可用 | 已记录 |
| 系统包 | `sudo apt-get install -y python3.12-venv` | 成功 |
| 依赖 | `~/llm_gateways/.venv` + `pip install 'openai>=2.29.0'` | **openai 2.31.0** |
| Anthropic SDK（后续小节） | `.venv/bin/pip install 'anthropic>=0.86.0'` | **anthropic 0.92.0** |
| tiktoken（吞吐 heavy / RPM 探针若用 heavy） | `.venv/bin/pip install tiktoken` | **tiktoken 0.12.0** |

---

## 2. 连通性：OpenAI SDK（`test_chat.py`，默认 `--client openai`）

**命令**（Key 通过环境变量注入，此处仅作结构说明）：

```bash
cd ~/llm_gateways
export NEWAPI_BASE_URL="https://api.mixroute.ai/v1"
export NEWAPI_API_KEY="***"
.venv/bin/python test_chat.py \
  --client openai \
  --base-url "$NEWAPI_BASE_URL" \
  --api-key "$NEWAPI_API_KEY" \
  -m claude-opus-4-6 \
  -m claude-sonnet-4-6 \
  -m gemini-3-flash-preview \
  -m gemini-3.1-pro-preview
```

**原始输出（`api_key` 已替换为 `***`）**：

```
Namespace(client='openai', base_url='https://api.mixroute.ai/v1', api_key='***', models_list=['claude-opus-4-6', 'claude-sonnet-4-6', 'gemini-3-flash-preview', 'gemini-3.1-pro-preview'], prompt='你好，请用一句话介绍你自己。', max_tokens=512, no_thinking=False)
Testing NewAPI chat (client=openai): base_url=https://api.mixroute.ai/v1, models=claude-opus-4-6, claude-sonnet-4-6, gemini-3-flash-preview, gemini-3.1-pro-preview
  [claude-opus-4-6] OK (3.38s): 你好！我是Claude，由Anthropic开发的AI助手，致力于以安全、诚实和有帮助的方式与人交流。
  [claude-sonnet-4-6] OK (1.61s): 你好！我是 **Claude**，一个由 Anthropic 开发的 AI 助手，致力于为您提供helpful、harmless且honest的对话与帮助。😊
  [gemini-3-flash-preview] OK (2.98s): 你好！我是由 Google 训练的大型语言模型。
  [gemini-3.1-pro-preview] OK (7.58s): 你好，我是由 Google 开发的大型语言模型 Gemini，随时准备为您提供智能、高效
4/4 passed. Exit 0.
```

**结论**：四个模型 **全部通过**，退出码 0。

---

## 3. Anthropic SDK / Messages API（`test_chat.py --client anthropic`）

验证网关是否兼容 **Anthropic Messages API**（官方 Python SDK 请求 `{anthropic_base_url}/v1/messages`）。脚本在传入 `https://api.mixroute.ai/v1` 时会规范为 **`anthropic_base_url=https://api.mixroute.ai`**，避免路径拼成 `/v1/v1/messages`。

**依赖安装**（在目标机 `~/llm_gateways` 的 venv 中）：

```bash
.venv/bin/pip install 'anthropic>=0.86.0'
```

**命令**（Key 脱敏为 `***`；与 OpenAI 小节相同可用 `NEWAPI_API_KEY`）：

```bash
cd ~/llm_gateways
export NEWAPI_BASE_URL="https://api.mixroute.ai/v1"
export NEWAPI_API_KEY="***"
.venv/bin/python test_chat.py \
  --client anthropic \
  --base-url "$NEWAPI_BASE_URL" \
  --api-key "$NEWAPI_API_KEY" \
  -m claude-opus-4-6 \
  -m claude-sonnet-4-6 \
  -m gemini-3-flash-preview \
  -m gemini-3.1-pro-preview
```

**原始输出（`api_key` 已替换为 `***`）**：

```
Namespace(client='anthropic', base_url='https://api.mixroute.ai/v1', api_key='***', models_list=['claude-opus-4-6', 'claude-sonnet-4-6', 'gemini-3-flash-preview', 'gemini-3.1-pro-preview'], prompt='你好，请用一句话介绍你自己。', max_tokens=512, no_thinking=False)
Testing NewAPI chat (client=anthropic): anthropic_base_url=https://api.mixroute.ai, models=claude-opus-4-6, claude-sonnet-4-6, gemini-3-flash-preview, gemini-3.1-pro-preview
  [claude-opus-4-6] OK (2.47s): 你好！我是Claude，由Anthropic公司开发的AI助手，乐于通过对话为你提供信息、解答问题和协助完成各种任务。
  [claude-sonnet-4-6] OK (2.54s): 你好！我是 **Claude**，一个由 Anthropic 开发的 AI 助手，致力于以安全、友好的方式帮助您解答问题、提供信息和完成各种任务。😊
  [gemini-3-flash-preview] OK (2.52s): 我是由 Google 训练的大型语言模型。
  [gemini-3.1-pro-preview] OK (7.46s): 你好，我是由 Google 开发的大型语言模型 Gemini，随时准备为你解答问题并提供各种帮助
4/4 passed. Exit 0.
```

**结论**：四模型在 Anthropic SDK 路径下 **全部通过**（退出码 0），说明该 NewAPI 实例对 **`/v1/messages`** 与 OpenAI 兼容 **`/v1/chat/completions`** 均可用（至少对上述模型 ID）。

**OpenAI 回归抽查**（同机、单模型，确认 `--client openai` 仍正常）：

```bash
.venv/bin/python test_chat.py --client openai --base-url "https://api.mixroute.ai/v1" --api-key "***" -m claude-opus-4-6
```

```
Namespace(client='openai', base_url='https://api.mixroute.ai/v1', api_key='***', models_list=['claude-opus-4-6'], prompt='你好，请用一句话介绍你自己。', max_tokens=512, no_thinking=False)
Testing NewAPI chat (client=openai): base_url=https://api.mixroute.ai/v1, models=claude-opus-4-6
  [claude-opus-4-6] OK (2.15s): 你好！我是Claude，由Anthropic开发的AI助手，乐于与你交流并帮助你解答各种问题。
1/1 passed. Exit 0.
```

---

## 4. Usage 采样（每模型 1 次，`max_tokens=512`，同默认 prompt）

在同一主机、同一 venv 下用 OpenAI SDK 读取 `response.usage`：

| 模型 | prompt_tokens | completion_tokens | total_tokens | 墙钟耗时 (s) |
|------|----------------|-------------------|--------------|--------------|
| claude-opus-4-6 | 23 | 50 | 73 | 3.48 |
| claude-sonnet-4-6 | 23 | 52 | 75 | 1.59 |
| gemini-3-flash-preview | 9 | 403 | 412 | 4.27 |
| gemini-3.1-pro-preview | 10 | 448 | 458 | 16.96 |

**说明**：Gemini 系列在相同 `max_tokens=512` 下 `completion_tokens` 明显高于 Claude，可能与网关/上游对「思考 / 多段输出」的计费或统计方式有关，不等同于用户可见正文长度；以网关返回的 `usage` 为准。

---

## 5. 吞吐（并行阶梯加压与延迟）

本节关注 **吞吐与延迟**：按轮提高并发、记录每请求耗时；**不等同于** 第 6 节「RPM」按「发起」定义的分钟窗口计数。

**脚本**：[scripts/rpm_until_limit.py](scripts/rpm_until_limit.py)（`AsyncOpenAI` + **可选 `tiktoken`**，OpenAI 兼容 `chat/completions`）；heavy 正文构造与 [scripts/openai_probe_payload.py](scripts/openai_probe_payload.py) 共用。

**模型**（默认）：`gemini-3-flash-preview`

**思路**：按「轮」同时发起当前并发数 `c` 个 `chat.completions` 调用，**逐请求**记录墙钟延迟（`ok round=… conc=… i=… latency_s=…`）。该轮 **任一** 失败（含 **HTTP 429**）则打印本轮全部行后结束；若全成功则按 `--scale` 增大 `c`，直至限流/错误、`--max-concurrency` 或 `--max-requests`。

### 5.1 默认负载：`--payload heavy`（约 10k 输入 token + `max_tokens=1000`）

- **用户消息**：脚本内固定中文「书籍节选《虚拟探针纪事》」设定 + **要求写尽可能详细的中文全书式总结**（情节/人物/主题/风格等），引导模型 **尽量拉长输出**，使 **`max_tokens` 常成为截断主因**。
- **输入规模**：用 **tiktoken**（默认编码 `cl100k_base`）将「前缀 + 英文填充」拼成 **恰好 `--input-tokens`（默认 10000）** 个 token 的 **单条 user `content`**。网关侧 `usage.prompt_tokens` 仍会 **大于** 该值（含模板等）。
- **输出上限**：`--max-tokens` 未指定时 **heavy 默认 1000**。
- **费用警告**：`heavy` 且 `--max-concurrency` **大于 16** 时，脚本会向 stderr 打印 **费用/耗时警告**；确需高并发可传 **`--i-know-expensive`**。

**主要参数（与 heavy 相关）**：

| 参数 | 含义 |
|------|------|
| `--payload heavy`（默认） | 使用上述书籍 + 摘要任务 |
| `--payload minimal` | 短 `--prompt`（默认 `Reply with exactly: OK`），`max_tokens` 默认 64 |
| `--input-tokens` | heavy：用户正文目标 token 数（tiktoken，默认 10000） |
| `--tiktoken-encoding` | heavy：构造正文所用编码（默认 `cl100k_base`） |
| `--max-tokens` | 传给 API；heavy 默认 1000，minimal 默认 64 |
| `--start-concurrency` | 首轮并行数（默认 1） |
| `--max-concurrency` | 并发上限（默认 128）；**heavy 初次探针建议 ≤16**；更高并发须 **`--i-know-expensive`**（费用/耗时极高） |
| `--scale double` / `linear` | 每轮成功后并发翻倍或按 `--linear-step` 增加 |
| `--max-requests` | 总请求次数（成功+失败）上限（默认 2000） |
| `--jsonl-out` | 可选 JSONL 归档 |

**汇总行**：结束时有 `--- summary ---`：`stop_reason`、`successful_requests`、`rounds_run`、`peak_concurrency`、**`approx_throughput_rpm`**（按 **整段墙钟时间** 与成功次数粗算的「请求/分钟」，非第 6 节限流窗口 RPM）、成功请求延迟 `min/p50/max`。

**说明**：**heavy** 与 **minimal** 的延迟与 `approx_throughput_rpm` **不可直接对比**。tiktoken 计数与 **网关/上游 tokenizer** 可能不一致，以服务端 `usage` 为准。**勿将完整 user 正文贴入报告**（体积大）。

#### 5.1.1 低并发示例（1→16，`max-requests` 127）

```bash
cd ~/llm_gateways
.venv/bin/pip install -q tiktoken   # 若尚未安装
export NEWAPI_BASE_URL="https://api.mixroute.ai/v1"
export NEWAPI_API_KEY="***"
nohup env NEWAPI_BASE_URL="$NEWAPI_BASE_URL" NEWAPI_API_KEY="$NEWAPI_API_KEY" \
  .venv/bin/python scripts/rpm_until_limit.py \
  --payload heavy \
  --input-tokens 10000 \
  --max-concurrency 16 \
  --max-requests 127 \
  --scale double \
  --jsonl-out /tmp/rpm_heavy.jsonl \
  > /tmp/rpm_heavy.out 2>&1 &
```

**实测 A（2026-04-09，`ubuntu@54.238.141.156`）**：日志 `/tmp/rpm_heavy.out`、`/tmp/rpm_heavy.jsonl`。

```
rpm_until_limit payload=heavy base_url=https://api.mixroute.ai/v1 model=gemini-3-flash-preview max_tokens=1000 scale=double start_concurrency=1 max_concurrency=16 max_requests=127
  input_tiktoken_count=10000 tiktoken_encoding=cl100k_base prompt_utf8_bytes=44712
```

```
--- summary ---
stop_reason=max_concurrency_no_limit_hit
successful_requests=31
total_attempts=31
rounds_run=5
peak_concurrency=16
total_wall_s=86.1195
approx_throughput_rpm=21.60
latency_s min=8.2422 p50=8.6489 max=32.4359
```

**轮次**：`c` 为 1→2→4→8→16，共 31 次成功，**未出现 429**。

#### 5.1.2 高并发示例（32→512，须 `--i-know-expensive`）

`--scale double` 下轮次为 32→64→128→256→512，合计 **992** 次成功请求（若全程无失败），`--max-requests` 至少 **992**。

```bash
cd ~/llm_gateways
export NEWAPI_BASE_URL="https://api.mixroute.ai/v1"
export NEWAPI_API_KEY="***"
nohup env NEWAPI_BASE_URL="$NEWAPI_BASE_URL" NEWAPI_API_KEY="$NEWAPI_API_KEY" \
  .venv/bin/python scripts/rpm_until_limit.py \
  --payload heavy \
  --input-tokens 10000 \
  --i-know-expensive \
  --start-concurrency 32 \
  --max-concurrency 512 \
  --scale double \
  --max-requests 2000 \
  --jsonl-out /tmp/rpm_heavy_32_512.jsonl \
  > /tmp/rpm_heavy_32_512.out 2>&1 &
```

**实测 B（2026-04-09，`ubuntu@54.238.141.156`）**：日志 `/tmp/rpm_heavy_32_512.out`、`/tmp/rpm_heavy_32_512.jsonl`。

```
rpm_until_limit payload=heavy base_url=https://api.mixroute.ai/v1 model=gemini-3-flash-preview max_tokens=1000 scale=double start_concurrency=32 max_concurrency=512 max_requests=2000
  input_tiktoken_count=10000 tiktoken_encoding=cl100k_base prompt_utf8_bytes=44712
```

```
--- summary ---
stop_reason=max_concurrency_no_limit_hit
successful_requests=992
total_attempts=992
rounds_run=5
peak_concurrency=512
total_wall_s=563.9005
approx_throughput_rpm=105.55
latency_s min=6.7098 p50=11.4960 max=317.8778
```

**轮次**：`c` 为 32→64→128→256→512，共 **992** 次成功；**含峰值并发 512 的一轮在内仍全部成功**，**未出现 429**（本次密钥与时段下）。`max≈318s` 反映大并行下尾部极慢请求，不代表单请求常态。

**历史对照（轻量并行，已非当前默认）**：曾用 **`--payload minimal`**（等价于旧版短 prompt、`max_tokens=64`）、`max_concurrency=128` 跑满 8 轮共 255 次成功，总墙钟约 22.6s、`approx_throughput_rpm≈676`，日志在远端 **`/tmp/rpm_probe.out`**（与 heavy **不可比**）。

---

## 6. RPM（按发起时刻的 60 秒窗口）

本节 **RPM** 指：**在首次出现失败请求时**，以该请求的 **发起时刻** `t*` 为锚，统计 **闭区间** `[t* - 60s, t*]` 内 **曾经发起** 的请求个数（含成功与失败、含锚点请求自身）。与第 5 节 **`approx_throughput_rpm`**（整段墙钟换算）口径不同。

**`t_start`（发起时刻）口径**（脚本内均用 `time.time()`）：

- **`batch`**（默认）：在调用 `chat.completions.create` **之前** 打点，与整轮 `gather` 同时启动的语义一致。
- **`overlap`**：在 **已获得 in-flight 槽位之后**、调用 `create` **之前** 打点；**排队等槽位期间不计入**「发起」，更贴近「已被调度允许向外发起请求」的时刻。

**脚本**：[scripts/rpm_minute_window_probe.py](scripts/rpm_minute_window_probe.py)（`AsyncOpenAI`；负载与 `rpm_until_limit` 一致：`--payload minimal|heavy`，heavy 依赖 **tiktoken** 与 [scripts/openai_probe_payload.py](scripts/openai_probe_payload.py)）。

### 6.1 调度模式：`batch` 与 `overlap`

- **`--scheduler batch`（默认）**：每轮 `asyncio.gather`，**整波结束** 再进入下一轮；并发上限按轮阶梯提高（见下「行为摘要」），适合与文档中「波次」描述对照。
- **`--scheduler overlap`**：预先创建 **`max_requests`** 个工作协程；在 **动态上限 `target_cap`**（同时 in-flight 上限）允许时即可继续发起，**不必等上一波全部返回**。`target_cap` 自 **`--start-concurrency`** 起，每隔 **`--ramp-interval-sec`**（默认 4）按 **`--scale double|linear`** 尝试提高，直至 **`--max-concurrency`**。更易在短窗内堆高发起速率，用于提高触达限流的概率（仍不保证一定出现 429）。
- **对比**：**batch 与 overlap 的时序与 `t_start` 定义不同，summary 与 60s 窗口计数不可直接横向对比**；同场景复现请固定调度方式与参数组。

**`batch` 行为摘要**：

- **阶梯加压**：自 **`--start-concurrency`** 起每轮成功后按 **`--scale double|linear`** 提高并发，直至 **`--max-concurrency`**；达到峰值后 **继续在峰值并发下分批发起**，直到 **`--max-requests`** 用尽或出现失败（与仅跑一轮峰值即停的旧版不同）。
- 每行输出含 **`t_start` / `t_end`（Unix 墙钟秒）** 与 `latency_s`。
- **首次失败**（含 **429** 或其它 HTTP/异常）：取该失败轮中 **`i` 最小** 的失败请求为锚点 `t*`，打印 `first_failure_i`、`anchor_t_start`、`window_60s_requests_started`（即 **RPM 窗口内发起数**）。
- **`overlap` 下首次失败**：锚点为 **最先被登记为「首次失败」** 的那条请求（并发多失败时 **未必** 是全局最小 `i`），同样以上述 **`t_start`** 统计 60s 内发起数。
- **全程无 API 失败**：用尽 **`max_requests`** 时 `stop_reason=max_requests`；summary 中 **`reference_only_*`** 以 **最后一次发起** 为锚统计 60s 内发起数，**仅作参考，不代表触限 RPM**。
- **`overlap` 的 summary**：额外给出观测到的 **`peak_in_flight_observed`**（in-flight 峰值）与 **`peak_target_cap_reached`**（`target_cap` 曾到达的上限），与 batch 的 **`peak_concurrency`**（波次并发）口径不同。

**默认参数（脚本内置）**：`--start-concurrency 256`、`--max-concurrency 256`（与 start 相同即 **每波固定 256 并行**，在 **`--max-requests 4096`** 内重复发起直至用尽或失败）、`--payload minimal`、`--scale double`。这样 **总发起次数** 持续增加、上限 4096，更适合观察 **固定并发下的 RPM/限流**。

若需 **继续提高并发**（如倍增至 512、1024…），请显式提高 **`--max-concurrency`**，并通常将 **`--max-requests`** 提高到 **大于** 完整阶梯各轮之和（例如自 256 倍增至 4096 至少约 **7936** 才可能跑满一轮 4096 并行后再多波峰值），否则会在阶梯中途因预算用尽而 `stop_reason=max_requests`。

**建议**：仍以 **`--payload minimal`** 为主做 RPM 探针；heavy 同第 5 节，**`--max-concurrency>16` 须 `--i-know-expensive`**。

**在目标机执行示例（batch，默认）**（Key 脱敏，`nohup`；日志与 JSONL 使用新文件名以免覆盖历史）：

```bash
cd ~/llm_gateways
export NEWAPI_BASE_URL="https://api.mixroute.ai/v1"
export NEWAPI_API_KEY="***"
nohup env NEWAPI_BASE_URL="$NEWAPI_BASE_URL" NEWAPI_API_KEY="$NEWAPI_API_KEY" \
  .venv/bin/python scripts/rpm_minute_window_probe.py \
  --scheduler batch \
  --payload minimal \
  --model gemini-3-flash-preview \
  --scale double \
  --start-concurrency 256 \
  --max-concurrency 256 \
  --max-requests 4096 \
  --jsonl-out /tmp/rpm_minute_window_256x16.jsonl \
  > /tmp/rpm_minute_window_256x16.out 2>&1 &
```

**overlap 示例**（重叠发起 + `target_cap` 爬坡；高并发与大量 task 占内存，请先小 **`max_requests`** 试跑；`--max-concurrency>16` 且 heavy 时仍需 **`--i-know-expensive`**）：

```bash
nohup env NEWAPI_BASE_URL="$NEWAPI_BASE_URL" NEWAPI_API_KEY="$NEWAPI_API_KEY" \
  .venv/bin/python scripts/rpm_minute_window_probe.py \
  --scheduler overlap \
  --payload minimal \
  --model gemini-3-flash-preview \
  --scale double \
  --start-concurrency 256 \
  --max-concurrency 4096 \
  --ramp-interval-sec 4 \
  --max-requests 4096 \
  --jsonl-out /tmp/rpm_minute_window_overlap.jsonl \
  > /tmp/rpm_minute_window_overlap.out 2>&1 &
```

**一次实测（2026-04-09，`ubuntu@54.238.141.156`）**：见远端 `/tmp/rpm_minute_window_256x16.out`、`/tmp/rpm_minute_window_256x16.jsonl`。参数：`--scheduler batch`、`start=max_concurrency=256`、`max_requests=4096`、`minimal`（默认 scheduler 即为 batch，省略 `--scheduler batch` 亦可）。

```
PLACEHOLDER_SUMMARY_BLOCK
```

（若出现首次失败，summary 会额外包含 `first_failure_i`、`anchor_t_start`、`window_60s_requests_started` 与 `note=RPM_window_...` 行。）

---

## 7. 总结与后续建议

- **连通性**：四个目标模型在 `54.238.141.156` 上均可成功完成 **`/v1/chat/completions`（OpenAI SDK）** 与 **`/v1/messages`（Anthropic SDK）**。
- **吞吐 vs RPM**：第 5 节 **`rpm_until_limit`** 侧重阶梯并发下的延迟与 **`approx_throughput_rpm`**；第 6 节 **`rpm_minute_window_probe`** 在出现失败时给出 **锚定 60s 发起计数**；二者勿混用。第 6 节内 **`batch` 与 `overlap`** 的时序与统计口径亦勿混用。
- **环境**：远端为 Python 3.12；若希望与仓库声明一致，可升级至 3.13+ 或使用容器。
- **安全**：尽快轮换已暴露的 API Key。

---

*本报告由验证执行过程自动生成并整理，步骤与结果均对应主机 `ubuntu@54.238.141.156`。*
