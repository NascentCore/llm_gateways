"""
测试 NewAPI LLM 网关：支持 OpenAI SDK（/v1/chat/completions）与 Anthropic SDK（/v1/messages）。

可指定：网关地址（--base-url）、API Key（--api-key）、客户端类型（--client）、待测模型（--models / -m）。
OpenAI 模式下 --base-url 通常带 /v1；Anthropic SDK 会自行请求 {base}/v1/messages，故传入 .../v1 时会自动去掉末尾 /v1，避免 /v1/v1/messages。
API Key：NEWAPI_API_KEY / OPENAI_API_KEY；Anthropic 模式还可使用 ANTHROPIC_API_KEY。勿将 Key 提交到仓库。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    import openai

DEFAULT_BASE_URL = "https://llm.sxwl.ai/v1"
DEFAULT_PROMPT = "你好，请用一句话介绍你自己。"
DEFAULT_MAX_TOKENS = 512  # 推理模型（如 Kimi K2.5）需更多 token 用于 reasoning + 回复


def _normalize_base_url(url: str) -> str:
    """去掉末尾斜杠；OpenAI 客户端在 base_url 下拼接 chat/completions。"""
    u = url.rstrip("/")
    return u or DEFAULT_BASE_URL


def _normalize_anthropic_base_url(url: str) -> str:
    """Anthropic SDK 固定 POST /v1/messages；若传入 .../v1 则去掉末尾 /v1，避免重复路径段。"""
    u = url.rstrip("/")
    if u.endswith("/v1"):
        u = u[:-3].rstrip("/")
    return u or "https://api.anthropic.com"


def _run_one(
    client: openai.OpenAI,
    model: str,
    prompt: str,
    max_tokens: int,
    extra_body: dict | None = None,
) -> tuple[bool, str, float]:
    """对单个模型发起一次 OpenAI 兼容 chat 请求。返回 (成功, 消息, 耗时秒)。"""
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


def _anthropic_text_preview(msg: object) -> str:
    """从 Messages API 的 Message 中拼接 text 类型 content 块。"""
    parts: list[str] = []
    content = getattr(msg, "content", None) or []
    for block in content:
        btype = getattr(block, "type", None)
        if btype == "text":
            t = getattr(block, "text", None) or ""
            if t:
                parts.append(t.strip())
    text = "\n".join(parts).strip()
    if not text:
        return "(无文本块)"
    return text[:80] + "..." if len(text) > 80 else text


def _run_one_anthropic(
    client: "anthropic.Anthropic",
    model: str,
    prompt: str,
    max_tokens: int,
    thinking: dict | None,
) -> tuple[bool, str, float]:
    """对单个模型发起一次 Anthropic Messages 请求。返回 (成功, 消息, 耗时秒)。"""
    start = time.perf_counter()
    try:
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if thinking is not None:
            kwargs["thinking"] = thinking
        resp = client.messages.create(**kwargs)
        elapsed = time.perf_counter() - start
        preview = _anthropic_text_preview(resp)
        return True, preview, elapsed
    except Exception as e:
        elapsed = time.perf_counter() - start
        return False, str(e), elapsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="使用 OpenAI 或 Anthropic 官方 SDK 测试 NewAPI 网关（chat/completions 或 messages）。"
    )
    parser.add_argument(
        "--client",
        choices=("openai", "anthropic"),
        default="openai",
        help="SDK 类型：openai=Chat Completions，anthropic=Messages API（默认 openai）",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("NEWAPI_BASE_URL", DEFAULT_BASE_URL),
        help="NewAPI 网关地址（默认: NEWAPI_BASE_URL 或 https://llm.sxwl.ai/v1）",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API Key（默认: NEWAPI_API_KEY 或 OPENAI_API_KEY；anthropic 模式还可读 ANTHROPIC_API_KEY）",
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
        help="OpenAI：extra_body thinking disabled；Anthropic：thinking type disabled。需网关/上游支持。",
    )
    args = parser.parse_args()

    api_key = args.api_key
    if api_key is None:
        api_key = os.environ.get("NEWAPI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key and args.client == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "错误: 未设置 API Key，请使用 --api-key 或环境变量 "
            "NEWAPI_API_KEY / OPENAI_API_KEY"
            + (" / ANTHROPIC_API_KEY（anthropic 模式）。" if args.client == "anthropic" else "。"),
            file=sys.stderr,
        )
        sys.exit(2)

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

    extra_body = {"thinking": {"type": "disabled"}} if args.no_thinking else None
    anthropic_thinking = {"type": "disabled"} if args.no_thinking else None

    if args.client == "openai":
        base_url = _normalize_base_url(args.base_url)
        header = (
            f"Testing NewAPI chat (client=openai): base_url={base_url}, "
            f"models={', '.join(models)}"
        )
        if extra_body:
            header += ", no-thinking=on"
    else:
        base_url = _normalize_anthropic_base_url(args.base_url)
        header = (
            f"Testing NewAPI chat (client=anthropic): anthropic_base_url={base_url}, "
            f"models={', '.join(models)}"
        )
        if anthropic_thinking:
            header += ", no-thinking=on"

    print(
        argparse.Namespace(
            client=args.client,
            base_url=args.base_url,
            api_key=api_key,
            models_list=models,
            prompt=args.prompt,
            max_tokens=args.max_tokens,
            no_thinking=args.no_thinking,
        )
    )
    print(header)

    passed = 0
    if args.client == "openai":
        from openai import OpenAI

        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            default_headers={"Accept": "application/json"},
        )
        for model in models:
            ok, msg, elapsed = _run_one(client, model, args.prompt, args.max_tokens, extra_body)
            if ok:
                print(f"  [{model}] OK ({elapsed:.2f}s): {msg}")
                passed += 1
            else:
                print(f"  [{model}] FAIL: {msg}")
    else:
        from anthropic import Anthropic

        client = Anthropic(
            base_url=base_url,
            api_key=api_key,
            default_headers={"Accept": "application/json"},
        )
        for model in models:
            ok, msg, elapsed = _run_one_anthropic(
                client, model, args.prompt, args.max_tokens, anthropic_thinking
            )
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
