"""
OpenAI 兼容的 Mock Chat Completions 服务。
用于压测：可配置「输出 token 数」，请求体按输入估算 token。
"""
import os
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock OpenAI Chat API", version="1.0")

# 约 1 token ≈ 4 字符（英文），用空格+字符填充以更接近真实
CHARS_PER_TOKEN = 4

# 从环境变量读取默认输出 token 数（可被请求中的 max_tokens 覆盖）
DEFAULT_OUTPUT_TOKENS = int(os.environ.get("MOCK_OUTPUT_TOKENS", "64"))
# 单次 completion 最大 token 上限（防止误传极大值占满内存；压测大 output 时需调大）
MAX_COMPLETION_TOKENS = int(os.environ.get("MOCK_MAX_COMPLETION_TOKENS", "262144"))


def _estimate_input_tokens(body: bytes) -> int:
    """根据请求体大小粗略估算 input token 数。"""
    return max(1, len(body) // CHARS_PER_TOKEN)


def _make_content_tokens(num_tokens: int) -> str:
    """生成约等于 num_tokens 的 content 字符串。"""
    if num_tokens <= 0:
        return ""
    # 用 " x" 重复，便于统计且稳定
    chunk = " x"
    repeat = (num_tokens * CHARS_PER_TOKEN) // len(chunk)
    return (chunk * repeat)[: num_tokens * CHARS_PER_TOKEN].strip() or "x"


def _estimate_prompt_tokens_from_body(body: dict) -> int:
    """从已解析的 body 估算 prompt token 数。"""
    import json
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    return _estimate_input_tokens(raw)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    """OpenAI 兼容的 chat completions：接收请求，按配置输出指定数量 token。"""
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": str(e), "type": "invalid_request_error"}},
        )

    messages = body.get("messages") or []
    max_tokens = body.get("max_tokens")
    if max_tokens is not None:
        try:
            max_tokens = int(max_tokens)
        except (TypeError, ValueError):
            max_tokens = DEFAULT_OUTPUT_TOKENS
    else:
        max_tokens = DEFAULT_OUTPUT_TOKENS
    max_tokens = max(1, min(max_tokens, MAX_COMPLETION_TOKENS))

    prompt_tokens = _estimate_prompt_tokens_from_body(body)
    completion_tokens = max_tokens
    total_tokens = prompt_tokens + completion_tokens

    content = _make_content_tokens(completion_tokens)
    # 流式暂不实现，只返回非流式
    stream = body.get("stream", False)
    if stream:
        import json
        # 简单流式：单 chunk 返回，content 做 JSON 转义
        escaped = json.dumps(content)

        def stream_gen():
            yield f'data: {{"id":"mock","choices":[{{"delta":{{"content":{escaped}}},"index":0}}],"usage":null}}\n'
            yield f'data: {{"id":"mock","choices":[{{"delta":{{}},"index":0}}],"usage":{{"prompt_tokens":{prompt_tokens},"completion_tokens":{completion_tokens},"total_tokens":{total_tokens}}}}}\n'
            yield "data: [DONE]\n"

        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            stream_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    return JSONResponse(
        content={
            "id": "mock-" + str(int(time.time() * 1000)),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.get("model", "mock-model"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        }
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
