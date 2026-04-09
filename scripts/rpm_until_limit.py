"""
并行调用 OpenAI 兼容 chat/completions：按轮次逐步提高并发数，直到 HTTP 429、其它错误或触顶上限。

支持两种负载：minimal（短 prompt）与 heavy（tiktoken 精确构造约 N token 的「书籍节选 + 详细摘要」指令，配合较大 max_tokens）。
API Key：--api-key 或 NEWAPI_API_KEY / OPENAI_API_KEY，勿提交仓库。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, TextIO

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from openai_probe_payload import DEFAULT_PROMPT, build_heavy_user_content

DEFAULT_BASE_URL = "https://llm.sxwl.ai/v1"
DEFAULT_MODEL = "gemini-3-flash-preview"


def _normalize_base_url(url: str) -> str:
    u = url.rstrip("/")
    return u or DEFAULT_BASE_URL


async def _one_request(
    client: Any,
    req_id: int,
    round_idx: int,
    concurrency: int,
    model: str,
    prompt: str,
    max_tokens: int,
) -> tuple[str, int, int, int, float, Any]:
    """返回 (status, req_id, round_idx, concurrency, latency_s, error_or_none)。status 为 ok / fail。"""
    from openai import APIStatusError

    t0 = time.perf_counter()
    try:
        await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        elapsed = time.perf_counter() - t0
        return ("ok", req_id, round_idx, concurrency, elapsed, None)
    except APIStatusError as e:
        elapsed = time.perf_counter() - t0
        return ("fail", req_id, round_idx, concurrency, elapsed, e)
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return ("fail", req_id, round_idx, concurrency, elapsed, e)


def _next_concurrency(
    c: int, max_c: int, scale: str, linear_step: int
) -> int:
    if scale == "double":
        return min(c * 2, max_c)
    return min(c + linear_step, max_c)


def _write_jsonl(fp: TextIO, obj: dict) -> None:
    fp.write(json.dumps(obj, ensure_ascii=False) + "\n")
    fp.flush()


async def _async_main(args: argparse.Namespace) -> None:
    from openai import APIStatusError, AsyncOpenAI

    base_url = _normalize_base_url(args.base_url)
    jsonl_fp: TextIO | None = None
    if args.jsonl_out:
        jsonl_fp = open(args.jsonl_out, "a", encoding="utf-8")

    client = AsyncOpenAI(
        base_url=base_url,
        api_key=args.api_key,
        default_headers={"Accept": "application/json"},
    )

    latencies_ok: list[float] = []
    wall0 = time.perf_counter()
    stop_reason = "unknown"
    req_id = 0
    peak_concurrency = 0
    rounds_run = 0

    prompt_b = len(args.prompt.encode("utf-8"))
    print(
        f"rpm_until_limit payload={args.payload} base_url={base_url} model={args.model} "
        f"max_tokens={args.max_tokens} scale={args.scale} "
        f"start_concurrency={args.start_concurrency} max_concurrency={args.max_concurrency} "
        f"max_requests={args.max_requests}",
        flush=True,
    )
    if args.payload == "heavy":
        print(
            f"  input_tiktoken_count={args.input_tokens} "
            f"tiktoken_encoding={args.tiktoken_encoding} prompt_utf8_bytes={prompt_b}",
            flush=True,
        )
    else:
        print(f"  prompt_preview={args.prompt[:80]!r}...", flush=True)

    try:
        c = args.start_concurrency
        if c < 1:
            print("错误: start-concurrency 须 >= 1", file=sys.stderr)
            sys.exit(2)
        if c > args.max_concurrency:
            print("错误: start-concurrency 不能大于 max-concurrency", file=sys.stderr)
            sys.exit(2)

        round_idx = 0
        while True:
            remaining_budget = args.max_requests - req_id
            if remaining_budget <= 0:
                stop_reason = "max_requests"
                break

            this_c = min(c, remaining_budget)
            peak_concurrency = max(peak_concurrency, this_c)
            round_idx += 1
            rounds_run = round_idx

            tasks = [
                _one_request(
                    client,
                    req_id + 1 + k,
                    round_idx,
                    this_c,
                    args.model,
                    args.prompt,
                    args.max_tokens,
                )
                for k in range(this_c)
            ]
            results = await asyncio.gather(*tasks)

            round_failed = False
            first_fail_reason: str | None = None
            for row in sorted(results, key=lambda r: r[1]):
                status, rid, ridx, conc, elapsed, err = row
                if status == "ok":
                    latencies_ok.append(elapsed)
                    line = (
                        f"ok round={ridx} conc={conc} i={rid} latency_s={elapsed:.4f}"
                    )
                    print(line, flush=True)
                    if jsonl_fp:
                        _write_jsonl(
                            jsonl_fp,
                            {
                                "i": rid,
                                "round": ridx,
                                "concurrency": conc,
                                "ok": True,
                                "latency_s": round(elapsed, 6),
                            },
                        )
                else:
                    round_failed = True
                    if isinstance(err, APIStatusError):
                        sc = err.status_code
                        msg = (err.message or str(err))[:500]
                        line = (
                            f"fail round={ridx} conc={conc} i={rid} "
                            f"latency_s={elapsed:.4f} status={sc} msg={msg}"
                        )
                        sr = "429" if sc == 429 else f"http_{sc}"
                    else:
                        ename = type(err).__name__ if err else "Error"
                        em = str(err)[:500] if err else ""
                        line = (
                            f"fail round={ridx} conc={conc} i={rid} "
                            f"latency_s={elapsed:.4f} err={ename}: {em}"
                        )
                        sr = ename if err else "error"
                    print(line, flush=True)
                    if jsonl_fp:
                        rec: dict = {
                            "i": rid,
                            "round": ridx,
                            "concurrency": conc,
                            "ok": False,
                            "latency_s": round(elapsed, 6),
                        }
                        if isinstance(err, APIStatusError):
                            rec["status"] = err.status_code
                            rec["message"] = (err.message or str(err))[:500]
                        elif err is not None:
                            rec["error"] = type(err).__name__
                            rec["message"] = str(err)[:500]
                        _write_jsonl(jsonl_fp, rec)
                    if first_fail_reason is None:
                        first_fail_reason = sr

            req_id += this_c

            if round_failed:
                stop_reason = first_fail_reason or "error"
                break

            if this_c < c:
                stop_reason = "max_requests"
                break

            if c >= args.max_concurrency:
                stop_reason = "max_concurrency_no_limit_hit"
                break

            new_c = _next_concurrency(c, args.max_concurrency, args.scale, args.linear_step)
            if new_c <= c:
                stop_reason = "max_concurrency_no_limit_hit"
                break
            c = new_c

    finally:
        await client.close()
        if jsonl_fp:
            jsonl_fp.close()

    total_wall = time.perf_counter() - wall0
    n_ok = len(latencies_ok)
    approx_rpm = (60.0 * n_ok / total_wall) if total_wall > 0 else 0.0

    print("--- summary ---", flush=True)
    print(f"stop_reason={stop_reason}", flush=True)
    print(f"successful_requests={n_ok}", flush=True)
    print(f"total_attempts={req_id}", flush=True)
    print(f"rounds_run={rounds_run}", flush=True)
    print(f"peak_concurrency={peak_concurrency}", flush=True)
    print(f"total_wall_s={total_wall:.4f}", flush=True)
    print(f"approx_throughput_rpm={approx_rpm:.2f}", flush=True)
    if latencies_ok:
        print(
            f"latency_s min={min(latencies_ok):.4f} "
            f"p50={statistics.median(latencies_ok):.4f} "
            f"max={max(latencies_ok):.4f}",
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "并行 chat：按轮提高并发数，直至 429/错误或 max-concurrency / max-requests。"
        )
    )
    parser.add_argument(
        "--payload",
        choices=("minimal", "heavy"),
        default="heavy",
        help="minimal=短 prompt；heavy=约 input-tokens 的书籍节选+摘要指令（默认 heavy）",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("NEWAPI_BASE_URL", DEFAULT_BASE_URL),
        help="网关 base_url（默认 NEWAPI_BASE_URL）",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("NEWAPI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        help="API Key（默认 NEWAPI_API_KEY / OPENAI_API_KEY）",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型 id")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        metavar="N",
        help="传给 API 的 max_tokens；不设时 heavy 默认 1000，minimal 默认 64",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="仅 payload=minimal 时使用用户消息",
    )
    parser.add_argument(
        "--input-tokens",
        type=int,
        default=None,
        metavar="N",
        help="仅 payload=heavy：用户正文目标 token 数（tiktoken，默认 10000）",
    )
    parser.add_argument(
        "--tiktoken-encoding",
        default="cl100k_base",
        help="heavy 模式下构造正文所用编码（默认 cl100k_base）",
    )
    parser.add_argument(
        "--i-know-expensive",
        action="store_true",
        help="heavy 且 max_concurrency>16 时跳过费用/耗时警告",
    )
    parser.add_argument(
        "--start-concurrency",
        type=int,
        default=1,
        metavar="N",
        help="首轮并行请求数（默认 1）",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=128,
        metavar="N",
        help="并发数上限（默认 128）",
    )
    parser.add_argument(
        "--scale",
        choices=("double", "linear"),
        default="double",
        help="每轮成功后并发增长方式：double=翻倍，linear=加 linear-step（默认 double）",
    )
    parser.add_argument(
        "--linear-step",
        type=int,
        default=2,
        metavar="N",
        help="scale=linear 时每轮增加的并发数（默认 2）",
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        default=2000,
        metavar="N",
        help="总请求次数上限（成功+失败合计，默认 2000）",
    )
    parser.add_argument(
        "--jsonl-out",
        default=None,
        metavar="PATH",
        help="每轮结果 JSONL（可选）",
    )
    args = parser.parse_args()

    if not args.api_key:
        print(
            "错误: 未设置 API Key（--api-key 或 NEWAPI_API_KEY / OPENAI_API_KEY）",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.max_tokens is None:
        args.max_tokens = 1000 if args.payload == "heavy" else 64

    if args.payload == "heavy":
        if args.input_tokens is None:
            args.input_tokens = 10_000
        args.prompt = build_heavy_user_content(
            args.input_tokens, args.tiktoken_encoding
        )
        if args.max_concurrency > 16 and not args.i_know_expensive:
            print(
                "警告: payload=heavy 时单请求体与生成量较大，"
                "--max-concurrency>16 可能导致极高费用与耗时；"
                "建议改用 --max-concurrency 16（或更小），或显式传入 --i-know-expensive。",
                file=sys.stderr,
            )
    asyncio.run(_async_main(args))


if __name__ == "__main__":
    main()
