"""
Locust 压测：向 NewAPI 的 /v1/chat/completions 发起请求，按多组 input/output token case 分桶统计。
需设置环境变量 NEWAPI_BASE_URL、NEWAPI_API_KEY；可选 NEWAPI_MODEL、LOCUST_REQUEST_TIMEOUT。

压测结束时会根据 runner 统计与响应中的 usage 打印 RPM / TPM，并写入 locust_last_token_metrics.json
（供 summarize_run.py 展示）。仅适用于单机 headless；分布式 worker 上的 token 未汇总到 master。
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from locust import HttpUser, between, events, task

TOKEN_METRICS_FILE = "locust_last_token_metrics.json"

_t_metrics_lock = threading.Lock()
_sum_total_tokens = 0
_sum_prompt_tokens = 0
_sum_completion_tokens = 0
_usage_response_count = 0
_t0_perf: float | None = None


def _record_usage(usage: dict) -> None:
    global _sum_total_tokens, _sum_prompt_tokens, _sum_completion_tokens, _usage_response_count
    p = int(usage.get("prompt_tokens") or 0)
    c = int(usage.get("completion_tokens") or 0)
    raw_total = usage.get("total_tokens")
    if raw_total is not None:
        t = int(raw_total)
    else:
        t = p + c
    with _t_metrics_lock:
        _sum_total_tokens += t
        _sum_prompt_tokens += p
        _sum_completion_tokens += c
        _usage_response_count += 1


@events.test_start.add_listener
def _reset_token_metrics(environment, **_kw) -> None:
    global _sum_total_tokens, _sum_prompt_tokens, _sum_completion_tokens, _usage_response_count, _t0_perf
    with _t_metrics_lock:
        _sum_total_tokens = 0
        _sum_prompt_tokens = 0
        _sum_completion_tokens = 0
        _usage_response_count = 0
    _t0_perf = time.perf_counter()


@events.test_stop.add_listener
def _emit_rpm_tpm(environment, **_kw) -> None:
    global _t0_perf
    if _t0_perf is None:
        return
    elapsed = max(time.perf_counter() - _t0_perf, 1e-9)
    mins = elapsed / 60.0
    runner = environment.runner
    if runner is None:
        return
    total_req = runner.stats.total.num_requests
    rpm = total_req / mins

    with _t_metrics_lock:
        st = _sum_total_tokens
        sp = _sum_prompt_tokens
        sc = _sum_completion_tokens
        nu = _usage_response_count

    tpm_total = st / mins
    tpm_prompt = sp / mins
    tpm_completion = sc / mins

    payload = {
        "elapsed_sec": round(elapsed, 3),
        "total_requests": total_req,
        "responses_with_usage": nu,
        "sum_total_tokens": st,
        "sum_prompt_tokens": sp,
        "sum_completion_tokens": sc,
        "rpm_all_requests": round(rpm, 2),
        "tpm_total_tokens": round(tpm_total, 2),
        "tpm_prompt_tokens": round(tpm_prompt, 2),
        "tpm_completion_tokens": round(tpm_completion, 2),
    }
    out = Path.cwd() / TOKEN_METRICS_FILE
    try:
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass

    print("\n--- RPM / TPM（整段压测时间平均；TPM 来自响应 usage，仅统计含 usage 的成功响应）---")
    print(f"  时长:        {elapsed:.1f}s  ({mins:.4f} min)")
    print(f"  RPM:         {rpm:.2f}  （全部请求数 / 分钟）")
    print(f"  TPM(total):  {tpm_total:.2f}  （Σ usage.total_tokens / 分钟；缺省时为 prompt+completion）")
    print(f"  TPM(prompt): {tpm_prompt:.2f}  |  TPM(completion): {tpm_completion:.2f}")
    print(f"  含 usage 响应数: {nu} / 总请求 {total_req}")
    print(f"  指标已写入: {out}")

# 与 benchmark/mock/main.py 中 CHARS_PER_TOKEN 一致
CHARS_PER_TOKEN = 4

# (目标 input tokens 量级, max_tokens / output)
BENCH_CASES = [
    (2000, 100),
    (20000, 1000),
    (200000, 50000),
    (100, 2000),
    (1000, 20000),
    (50000, 200000),
]


def build_user_content(input_tokens: int) -> str:
    """生成约 input_tokens * 4 字节的 user content，与 Mock 对 prompt 的估算方式一致。"""
    if input_tokens <= 0:
        return "x"
    chunk = " x"
    repeat = (input_tokens * CHARS_PER_TOKEN) // len(chunk)
    return (chunk * repeat)[: input_tokens * CHARS_PER_TOKEN].strip() or "x"


# 启动时预计算各 input 档位的 content，避免每次请求分配超大字符串
_UNIQUE_INPUTS = sorted({c[0] for c in BENCH_CASES}, reverse=True)
CONTENT_BY_INPUT = {n: build_user_content(n) for n in _UNIQUE_INPUTS}

_DEFAULT_TIMEOUT = int(os.environ.get("LOCUST_REQUEST_TIMEOUT", "300"))


def _timeout_for_case(in_tok: int, out_tok: int) -> int:
    """大 body 或大 output 使用环境变量默认的长超时。"""
    if in_tok >= 50000 or out_tok >= 50000:
        return _DEFAULT_TIMEOUT
    return min(_DEFAULT_TIMEOUT, 120)


def _make_bench_task(in_tok: int, out_tok: int):
    endpoint_name = f"/v1/chat/completions in={in_tok} out={out_tok}"
    user_content = CONTENT_BY_INPUT[in_tok]
    req_timeout = _timeout_for_case(in_tok, out_tok)

    @task(1)
    def bench_task(self):
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": user_content}],
            "max_tokens": out_tok,
            "stream": False,
        }
        with self.client.post(
            "/v1/chat/completions",
            json=payload,
            name=endpoint_name,
            timeout=req_timeout,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("choices") and data.get("usage"):
                        _record_usage(data["usage"])
                        response.success()
                    else:
                        response.failure("Missing choices or usage")
                except Exception as e:
                    response.failure(str(e))
            else:
                response.failure(f"HTTP {response.status_code}")

    return bench_task


def _bench_tasks():
    """Locust 只认类上的 tasks 列表或在类体里定义的 @task；动态 setattr 无效，故在此构建列表。"""
    out = []
    for in_tok, out_tok in BENCH_CASES:
        fn = _make_bench_task(in_tok, out_tok)
        fn.__name__ = f"bench_in{in_tok}_out{out_tok}"
        out.append(fn)
    return out


class NewAPIChatUser(HttpUser):
    """模拟用户调用 NewAPI Chat Completions；各 task 对应不同 input/output token case。"""

    wait_time = between(0.5, 1.5)
    tasks = _bench_tasks()

    def on_start(self):
        self.host = os.environ.get("NEWAPI_BASE_URL", "http://localhost:3000").rstrip("/")
        self.api_key = os.environ.get("NEWAPI_API_KEY", "")
        self.model = os.environ.get("NEWAPI_MODEL", "mock-model")
        self.client.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
