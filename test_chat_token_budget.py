"""
使用 OpenAI SDK 发起 chat 请求，可指定「输入 token 数」与「最大输出 token 数」。

用户消息固定以指令「写一段长篇故事，越长越好」开头，其后为填充文本。
在**当前选用的 tiktoken 编码**下，发送前会校验 `len(encode(user.content))` **严格等于** `--input-tokens`；
若不相符则直接退出，不发起请求。服务端 `usage.prompt_tokens` 另含对话模板、system 等，一般大于该值。
API Key 勿提交仓库，可用 --api-key 或环境变量 NEWAPI_API_KEY / OPENAI_API_KEY。
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import tiktoken

DEFAULT_BASE_URL = "https://llm.sxwl.ai/v1"

# 置于用户消息开头，引导模型尽量长输出；与填充段在 token 边界拼接，保证总 token 数可控。
STORY_INSTRUCTION_PREFIX = "写一段长篇故事，越长越好\n\n"


def _normalize_base_url(url: str) -> str:
    u = url.rstrip("/")
    return u or DEFAULT_BASE_URL


def _get_encoding(model: str | None, encoding_name: str | None):
    if encoding_name:
        return tiktoken.get_encoding(encoding_name)
    if model:
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            pass
    return tiktoken.get_encoding("cl100k_base")


def build_user_content(target_tokens: int, enc, prefix: str) -> str:
    """构造用户消息：prefix 在前，不足部分用英文填充；token 在 id 空间拼接后 decode 一次。"""
    if target_tokens < 1:
        return ""
    prefix_ids = enc.encode(prefix)
    if len(prefix_ids) >= target_tokens:
        ids = prefix_ids[:target_tokens]
    else:
        rest = target_tokens - len(prefix_ids)
        filler = " The quick brown fox jumps over the lazy dog."
        fill_ids: list[int] = []
        while len(fill_ids) < rest:
            fill_ids.extend(enc.encode(filler))
        ids = prefix_ids + fill_ids[:rest]
    return enc.decode(ids)


def assert_user_content_token_count(enc, text: str, expected: int) -> None:
    """保证在 enc 下用户正文 token 数恰好为 expected；否则退出进程。"""
    actual = len(enc.encode(text))
    if actual != expected:
        print(
            f"错误: 用户消息在 tiktoken 编码「{enc.name}」下为 {actual} tokens，"
            f"与 --input-tokens={expected} 不一致（不应发生，请报 issue）。",
            file=sys.stderr,
        )
        sys.exit(3)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OpenAI SDK chat：指定输入 token 数与最大输出 token 数。"
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("NEWAPI_BASE_URL", DEFAULT_BASE_URL),
        help="网关 base URL（默认 NEWAPI_BASE_URL 或内置默认）",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("NEWAPI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        help="API Key（默认 NEWAPI_API_KEY 或 OPENAI_API_KEY）",
    )
    parser.add_argument(
        "--model",
        "-m",
        required=True,
        metavar="MODEL",
        help="模型名",
    )
    parser.add_argument(
        "--input-tokens",
        type=int,
        default=32,
        metavar="N",
        help="用户消息目标 token 数（含开头故事指令 + 填充；发送前在 tiktoken 下严格校验为恰好 N，默认 32）",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=64,
        metavar="N",
        help="max_tokens：单次回复上限（默认 64）",
    )
    parser.add_argument(
        "--encoding",
        default=None,
        metavar="NAME",
        help="tiktoken 编码名（如 cl100k_base、o200k_base）；不设则尽量按 --model 推断",
    )
    parser.add_argument(
        "--system",
        default=None,
        help="可选 system 消息；会额外占用上下文，不计入 --input-tokens",
    )
    parser.add_argument(
        "--echo-stats",
        action="store_true",
        help="打印 usage（若响应含 usage）",
    )
    args = parser.parse_args()

    if not args.api_key:
        print(
            "错误: 未设置 API Key，请使用 --api-key 或环境变量 NEWAPI_API_KEY / OPENAI_API_KEY。",
            file=sys.stderr,
        )
        sys.exit(2)

    enc = _get_encoding(args.model, args.encoding)
    prefix = STORY_INSTRUCTION_PREFIX
    prefix_tok = len(enc.encode(prefix))
    if prefix_tok > args.input_tokens:
        print(
            f"注意: 故事指令占 {prefix_tok} tokens，大于 --input-tokens={args.input_tokens}，"
            "开头指令将被截断至恰好 N tokens。",
            file=sys.stderr,
        )
    user_text = build_user_content(args.input_tokens, enc, prefix)
    assert_user_content_token_count(enc, user_text, args.input_tokens)

    messages: list[dict[str, str]] = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": user_text})

    base_url = _normalize_base_url(args.base_url)
    print(
        f"请求: base_url={base_url}, model={args.model}, "
        f"user_content_tokens={args.input_tokens} (tiktoken {enc.name}), "
        f"max_output_tokens={args.max_output_tokens}"
    )

    from openai import OpenAI

    client = OpenAI(
        base_url=base_url,
        api_key=args.api_key,
        default_headers={"Accept": "application/json"},
    )

    start = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=args.model,
            messages=messages,
            max_tokens=args.max_output_tokens,
        )
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"FAIL ({elapsed:.2f}s): {e}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.perf_counter() - start
    choice = resp.choices[0] if resp.choices else None
    content = (choice.message.content or "").strip() if choice and choice.message else ""
    preview = (content[:120] + "…") if len(content) > 120 else content
    print(f"OK ({elapsed:.2f}s): {preview or '(空回复)'}")

    if args.echo_stats and getattr(resp, "usage", None):
        u = resp.usage
        pt = getattr(u, "prompt_tokens", None)
        print(
            "usage:",
            f"prompt_tokens={pt}, "
            f"completion_tokens={getattr(u, 'completion_tokens', None)}, "
            f"total_tokens={getattr(u, 'total_tokens', None)}",
        )
        if pt is not None and pt != args.input_tokens:
            print(
                f"说明: prompt_tokens({pt}) 含消息格式/system 等，"
                f"与用户正文 tiktoken 数({args.input_tokens}) 不同属正常。",
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
