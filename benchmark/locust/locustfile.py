"""
Locust 压测：向 NewAPI 的 /v1/chat/completions 发起请求，按多组 input/output token case 分桶统计。
需设置环境变量 NEWAPI_BASE_URL、NEWAPI_API_KEY；可选 NEWAPI_MODEL、LOCUST_REQUEST_TIMEOUT。
"""
import os
from locust import HttpUser, task, between

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
