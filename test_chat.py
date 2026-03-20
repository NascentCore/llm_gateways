"""
使用 OpenAI 客户端测试 NewAPI LLM 网关的 chat 接口（/v1/chat/completions）。

可指定：NewAPI 地址（--base-url）、API Key（--api-key）、待测模型列表（--models 或 -m）。
API Key 可从环境变量 NEWAPI_API_KEY 或 OPENAI_API_KEY 读取，勿将 Key 提交到仓库。
"""

import argparse
import os
import sys
import time
from typing import List

DEFAULT_BASE_URL = "https://llm.sxwl.ai/v1"
DEFAULT_PROMPT = "你好，请用一句话介绍你自己。"
DEFAULT_MAX_TOKENS = 512  # 推理模型（如 Kimi K2.5）需更多 token 用于 reasoning + 回复


def _normalize_base_url(url: str) -> str:
    """去掉末尾 /v1 或斜杠，避免客户端拼成 /v1/v1/..."""
    u = url.rstrip("/")
    return u or DEFAULT_BASE_URL


def _run_one(
    client: "openai.OpenAI",
    model: str,
    prompt: str,
    max_tokens: int,
    extra_body: dict | None = None,
) -> tuple[bool, str, float]:
    """对单个模型发起一次 chat 请求。返回 (成功, 消息, 耗时秒)。"""
    start = time.perf_counter()
    try:
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        if extra_body:
            kwargs["extra_body"] = extra_body
        resp = client.chat.completions.create(**kwargs)
        elapsed = time.perf_counter() - start
        if isinstance(resp, str):
            return False, f"API returned string instead of object: {resp[:200]}", elapsed
        if not hasattr(resp, "choices"):
            return False, f"Unexpected response type {type(resp).__name__}: {str(resp)[:200]}", elapsed
        if resp.choices:
            content = (resp.choices[0].message.content or "").strip()
            content_preview = content[:80] + "..." if len(content) > 80 else content
            return True, content_preview or "(空回复)", elapsed
        return True, "(无 content)", elapsed
    except Exception as e:
        elapsed = time.perf_counter() - start
        return False, str(e), elapsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="使用 OpenAI 客户端测试 NewAPI LLM 网关的 chat 接口。"
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("NEWAPI_BASE_URL", DEFAULT_BASE_URL),
        help="NewAPI 网关地址（默认: NEWAPI_BASE_URL 或 https://llm.sxwl.ai）",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("NEWAPI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        help="API Key（默认: NEWAPI_API_KEY 或 OPENAI_API_KEY）",
    )
    parser.add_argument(
        "--models",
        "-m",
        action="append",
        dest="models_list",
        metavar="MODEL",
        help="待测模型，可多次 -m 或逗号分隔的 --models model1,model2",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="测试用的用户消息内容",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        metavar="N",
        help="单次请求最大生成 token 数",
    )
    parser.add_argument(
        "--no-thinking",
        action="store_true",
        help="禁用推理模型的 thinking 模式（Kimi K2.5 等），传 extra_body={'thinking':{'type':'disabled'}}。需网关转发 extra_body 才生效。",
    )
    args = parser.parse_args()
    print(args)

    # 解析模型列表：-m a -m b 或 --models a,b
    models: List[str] = []
    if args.models_list:
        for part in args.models_list:
            models.extend(m.strip() for m in part.split(",") if m.strip())
    if not models:
        print(
            "错误: 请至少指定一个模型，例如 --models claude-sonnet-4-6 或 -m gpt-4o",
            file=sys.stderr,
        )
        sys.exit(2)

    api_key = args.api_key
    if not api_key:
        print(
            "错误: 未设置 API Key，请使用 --api-key 或环境变量 NEWAPI_API_KEY / OPENAI_API_KEY。",
            file=sys.stderr,
        )
        sys.exit(2)

    base_url = _normalize_base_url(args.base_url)
    extra_body = {"thinking": {"type": "disabled"}} if args.no_thinking else None
    if extra_body:
        print(f"Testing NewAPI chat: base_url={base_url}, models={', '.join(models)}, no-thinking=on")
    else:
        print(f"Testing NewAPI chat: base_url={base_url}, models={', '.join(models)}")

    from openai import OpenAI

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        default_headers={"Accept": "application/json"},
    )
    passed = 0
    for model in models:
        ok, msg, elapsed = _run_one(client, model, args.prompt, args.max_tokens, extra_body)
        if ok:
            print(f"  [{model}] OK ({elapsed:.2f}s): {msg}")
            passed += 1
        else:
            print(f"  [{model}] FAIL: {msg}")

    print(f"{passed}/{len(models)} passed.", end=" ")
    if passed == len(models):
        print("Exit 0.")
        sys.exit(0)
    print("Exit 1.")
    sys.exit(1)


if __name__ == "__main__":
    main()

