"""
RPM 探针（按「发起」计数）：阶梯提高并发上限，记录每请求发起/结束墙钟时间；
在首次失败时，以该请求发起时刻 t* 为锚，统计 [t*-60s, t*] 内发起的请求总数。

调度：
- batch：每轮 asyncio.gather，整波结束再进入下一轮（默认）。
- overlap：预先创建 max_requests 个协程，在槽位允许时重叠发起 HTTP，target_cap 按间隔翻倍/线性增长。

与 rpm_until_limit（吞吐/延迟）统计口径不同；API Key 勿提交仓库。
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
WINDOW_SEC = 60.0
OVERLAP_ROUND_TAG = 0  # 日志中 round=0 表示 overlap 调度


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
) -> tuple[str, int, int, int, float, float, float, Any]:
    """status, req_id, round, conc, t_start, t_end, latency_s, err."""
    from openai import APIStatusError

    t_start = time.time()
    t0 = time.perf_counter()
    try:
        await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        t_end = time.time()
        elapsed = time.perf_counter() - t0
        return ("ok", req_id, round_idx, concurrency, t_start, t_end, elapsed, None)
    except APIStatusError as e:
        t_end = time.time()
        elapsed = time.perf_counter() - t0
        return ("fail", req_id, round_idx, concurrency, t_start, t_end, elapsed, e)
    except Exception as e:
        t_end = time.time()
        elapsed = time.perf_counter() - t0
        return ("fail", req_id, round_idx, concurrency, t_start, t_end, elapsed, e)


def _next_concurrency(c: int, max_c: int, scale: str, linear_step: int) -> int:
    if scale == "double":
        return min(c * 2, max_c)
    return min(c + linear_step, max_c)


def _write_jsonl(fp: TextIO, obj: dict) -> None:
    fp.write(json.dumps(obj, ensure_ascii=False) + "\n")
    fp.flush()


def _count_starts_in_window(records: list[dict], anchor_t_start: float) -> int:
    lo = anchor_t_start - WINDOW_SEC
    hi = anchor_t_start
    return sum(1 for r in records if lo <= r["t_start"] <= hi)


def _print_header(args: argparse.Namespace, base_url: str, prompt_b: int) -> None:
    print(
        f"rpm_minute_window_probe scheduler={args.scheduler} payload={args.payload} "
        f"base_url={base_url} model={args.model} "
        f"max_tokens={args.max_tokens} scale={args.scale} "
        f"start_concurrency={args.start_concurrency} max_concurrency={args.max_concurrency} "
        f"max_requests={args.max_requests} window_sec={WINDOW_SEC}",
        flush=True,
    )
    if args.scheduler == "overlap":
        print(f"  ramp_interval_sec={args.ramp_interval_sec}", flush=True)
    if args.payload == "heavy":
        print(
            f"  input_tiktoken_count={args.input_tokens} "
            f"tiktoken_encoding={args.tiktoken_encoding} prompt_utf8_bytes={prompt_b}",
            flush=True,
        )
    else:
        print(f"  prompt_preview={args.prompt[:80]!r}...", flush=True)


def _print_summary(
    *,
    stop_reason: str,
    n_ok: int,
    req_id: int,
    rounds_run: int | str,
    peak_concurrency: int,
    peak_in_flight: int | None,
    peak_target_cap: int | None,
    total_wall: float,
    first_failure_i: int | None,
    first_failure_anchor_t: float | None,
    window_60s_starts: int | None,
    all_records: list[dict],
    latencies_ok: list[float],
    scheduler: str,
) -> None:
    print("--- summary ---", flush=True)
    print(f"stop_reason={stop_reason}", flush=True)
    print(f"successful_requests={n_ok}", flush=True)
    print(f"total_attempts={req_id}", flush=True)
    print(f"rounds_run={rounds_run}", flush=True)
    print(f"peak_concurrency={peak_concurrency}", flush=True)
    if scheduler == "overlap" and peak_in_flight is not None and peak_target_cap is not None:
        print(
            f"peak_in_flight_observed={peak_in_flight} peak_target_cap_reached={peak_target_cap}",
            flush=True,
        )
    print(f"total_wall_s={total_wall:.4f}", flush=True)
    approx_rpm = (60.0 * n_ok / total_wall) if total_wall > 0 else 0.0
    print(f"approx_throughput_rpm={approx_rpm:.2f}", flush=True)
    if first_failure_i is not None and first_failure_anchor_t is not None:
        print(
            f"first_failure_i={first_failure_i} "
            f"anchor_t_start={first_failure_anchor_t:.6f} "
            f"window_{int(WINDOW_SEC)}s_requests_started={window_60s_starts}",
            flush=True,
        )
        print(
            "note=RPM_window_counts_requests_whose_t_start_falls_in_[anchor-60s,anchor]",
            flush=True,
        )
    else:
        if all_records:
            last = all_records[-1]
            ref_anchor = last["t_start"]
            ref_count = _count_starts_in_window(all_records, ref_anchor)
            print(
                f"reference_only_last_start_t={ref_anchor:.6f} "
                f"window_{int(WINDOW_SEC)}s_requests_started={ref_count} "
                f"(no API failure; stop={stop_reason}; not a rate-limit RPM)",
                flush=True,
            )
    if latencies_ok:
        print(
            f"latency_s min={min(latencies_ok):.4f} "
            f"p50={statistics.median(latencies_ok):.4f} "
            f"max={max(latencies_ok):.4f}",
            flush=True,
        )


async def _async_main_batch(
    client: Any,
    args: argparse.Namespace,
    jsonl_fp: TextIO | None,
) -> None:
    all_records: list[dict] = []
    latencies_ok: list[float] = []
    wall0 = time.perf_counter()
    stop_reason = "unknown"
    req_id = 0
    peak_concurrency = 0
    rounds_run = 0
    first_failure_anchor_t: float | None = None
    first_failure_i: int | None = None
    window_60s_starts: int | None = None

    from openai import APIStatusError

    c = args.start_concurrency
    round_idx = 0
    at_peak = False
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
            (
                status,
                rid,
                ridx,
                conc,
                t_start,
                t_end,
                elapsed,
                err,
            ) = row
            rec: dict = {
                "i": rid,
                "round": ridx,
                "concurrency": conc,
                "ok": status == "ok",
                "t_start": t_start,
                "t_end": t_end,
                "latency_s": round(elapsed, 6),
                "scheduler": "batch",
            }
            if status == "ok":
                latencies_ok.append(elapsed)
                line = (
                    f"ok round={ridx} conc={conc} i={rid} "
                    f"t_start={t_start:.6f} t_end={t_end:.6f} latency_s={elapsed:.4f}"
                )
                print(line, flush=True)
            else:
                round_failed = True
                if isinstance(err, APIStatusError):
                    sc = err.status_code
                    msg = (err.message or str(err))[:500]
                    rec["status"] = sc
                    rec["message"] = msg
                    line = (
                        f"fail round={ridx} conc={conc} i={rid} "
                        f"t_start={t_start:.6f} t_end={t_end:.6f} latency_s={elapsed:.4f} "
                        f"status={sc} msg={msg}"
                    )
                    sr = "429" if sc == 429 else f"http_{sc}"
                else:
                    ename = type(err).__name__ if err else "Error"
                    em = str(err)[:500] if err else ""
                    rec["error"] = ename
                    rec["message"] = em
                    line = (
                        f"fail round={ridx} conc={conc} i={rid} "
                        f"t_start={t_start:.6f} t_end={t_end:.6f} latency_s={elapsed:.4f} "
                        f"err={ename}: {em}"
                    )
                    sr = ename if err else "error"
                print(line, flush=True)
                if first_fail_reason is None:
                    first_fail_reason = sr

            all_records.append(rec)
            if jsonl_fp:
                _write_jsonl(jsonl_fp, rec)

        req_id += this_c

        if round_failed:
            stop_reason = first_fail_reason or "error"
            failed = [r for r in results if r[0] == "fail"]
            anchor = min(failed, key=lambda r: r[1])
            first_failure_i = anchor[1]
            first_failure_anchor_t = anchor[4]
            window_60s_starts = _count_starts_in_window(
                all_records, first_failure_anchor_t
            )
            break

        if this_c < c and not at_peak:
            stop_reason = "max_requests"
            break

        if at_peak:
            continue

        if c >= args.max_concurrency:
            at_peak = True
            c = args.max_concurrency
            continue

        new_c = _next_concurrency(c, args.max_concurrency, args.scale, args.linear_step)
        if new_c <= c:
            at_peak = True
            c = min(c, args.max_concurrency)
            continue
        c = new_c

    total_wall = time.perf_counter() - wall0
    _print_summary(
        stop_reason=stop_reason,
        n_ok=len(latencies_ok),
        req_id=req_id,
        rounds_run=rounds_run,
        peak_concurrency=peak_concurrency,
        peak_in_flight=None,
        peak_target_cap=None,
        total_wall=total_wall,
        first_failure_i=first_failure_i,
        first_failure_anchor_t=first_failure_anchor_t,
        window_60s_starts=window_60s_starts,
        all_records=all_records,
        latencies_ok=latencies_ok,
        scheduler="batch",
    )


async def _async_main_overlap(
    client: Any,
    args: argparse.Namespace,
    jsonl_fp: TextIO | None,
) -> None:
    from openai import APIStatusError

    all_records: list[dict] = []
    latencies_ok: list[float] = []
    wall0 = time.perf_counter()

    cond = asyncio.Condition()
    in_flight = 0
    target_cap = args.start_concurrency
    stop = False
    stop_reason = "unknown"
    peak_in_flight = 0
    peak_target_cap = args.start_concurrency
    first_failure_i: int | None = None
    first_failure_anchor_t: float | None = None

    async def ramp_loop() -> None:
        nonlocal target_cap, peak_target_cap, stop
        while True:
            await asyncio.sleep(args.ramp_interval_sec)
            async with cond:
                if stop:
                    break
                new_c = _next_concurrency(
                    target_cap, args.max_concurrency, args.scale, args.linear_step
                )
                if new_c > target_cap:
                    target_cap = new_c
                    peak_target_cap = max(peak_target_cap, target_cap)
                cond.notify_all()

    async def worker(req_id: int) -> None:
        nonlocal in_flight, stop, stop_reason, peak_in_flight
        nonlocal first_failure_i, first_failure_anchor_t
        cap_snap = 0
        async with cond:
            while not stop and in_flight >= target_cap:
                await cond.wait()
            if stop:
                return
            in_flight += 1
            peak_in_flight = max(peak_in_flight, in_flight)
            cap_snap = target_cap

        t_start = time.time()
        t0 = time.perf_counter()
        err: Any = None
        status = "ok"
        try:
            await client.chat.completions.create(
                model=args.model,
                messages=[{"role": "user", "content": args.prompt}],
                max_tokens=args.max_tokens,
            )
        except APIStatusError as e:
            status = "fail"
            err = e
        except Exception as e:
            status = "fail"
            err = e
        t_end = time.time()
        elapsed = time.perf_counter() - t0

        rec: dict = {
            "i": req_id,
            "round": OVERLAP_ROUND_TAG,
            "concurrency": cap_snap,
            "ok": status == "ok",
            "t_start": t_start,
            "t_end": t_end,
            "latency_s": round(elapsed, 6),
            "scheduler": "overlap",
        }
        sr = ""
        if status == "ok":
            latencies_ok.append(elapsed)
            line = (
                f"ok sched=overlap round={OVERLAP_ROUND_TAG} conc={cap_snap} i={req_id} "
                f"t_start={t_start:.6f} t_end={t_end:.6f} latency_s={elapsed:.4f}"
            )
            print(line, flush=True)
        else:
            if isinstance(err, APIStatusError):
                sc = err.status_code
                msg = (err.message or str(err))[:500]
                rec["status"] = sc
                rec["message"] = msg
                line = (
                    f"fail sched=overlap round={OVERLAP_ROUND_TAG} conc={cap_snap} i={req_id} "
                    f"t_start={t_start:.6f} t_end={t_end:.6f} latency_s={elapsed:.4f} "
                    f"status={sc} msg={msg}"
                )
                sr = "429" if sc == 429 else f"http_{sc}"
            else:
                ename = type(err).__name__ if err else "Error"
                em = str(err)[:500] if err else ""
                rec["error"] = ename
                rec["message"] = em
                line = (
                    f"fail sched=overlap round={OVERLAP_ROUND_TAG} conc={cap_snap} i={req_id} "
                    f"t_start={t_start:.6f} t_end={t_end:.6f} latency_s={elapsed:.4f} "
                    f"err={ename}: {em}"
                )
                sr = ename if err else "error"
            print(line, flush=True)

        all_records.append(rec)
        if jsonl_fp:
            _write_jsonl(jsonl_fp, rec)

        async with cond:
            if status == "fail" and first_failure_i is None:
                first_failure_i = req_id
                first_failure_anchor_t = t_start
                stop_reason = sr
                stop = True
            in_flight -= 1
            cond.notify_all()

    ramp_task = asyncio.create_task(ramp_loop())
    worker_tasks = [
        asyncio.create_task(worker(i)) for i in range(1, args.max_requests + 1)
    ]
    try:
        await asyncio.gather(*worker_tasks)
    finally:
        async with cond:
            stop = True
            cond.notify_all()
        ramp_task.cancel()
        try:
            await ramp_task
        except asyncio.CancelledError:
            pass

    if first_failure_i is None:
        stop_reason = "max_requests"
    window_60s_starts: int | None = None
    if first_failure_anchor_t is not None:
        window_60s_starts = _count_starts_in_window(all_records, first_failure_anchor_t)

    total_wall = time.perf_counter() - wall0
    peak_conc = max(peak_in_flight, peak_target_cap)
    _print_summary(
        stop_reason=stop_reason,
        n_ok=len(latencies_ok),
        req_id=len(all_records),
        rounds_run="overlap",
        peak_concurrency=peak_conc,
        peak_in_flight=peak_in_flight,
        peak_target_cap=peak_target_cap,
        total_wall=total_wall,
        first_failure_i=first_failure_i,
        first_failure_anchor_t=first_failure_anchor_t,
        window_60s_starts=window_60s_starts,
        all_records=all_records,
        latencies_ok=latencies_ok,
        scheduler="overlap",
    )


async def _async_main(args: argparse.Namespace) -> None:
    from openai import AsyncOpenAI

    base_url = _normalize_base_url(args.base_url)
    jsonl_fp: TextIO | None = None
    if args.jsonl_out:
        jsonl_fp = open(args.jsonl_out, "a", encoding="utf-8")

    client = AsyncOpenAI(
        base_url=base_url,
        api_key=args.api_key,
        default_headers={"Accept": "application/json"},
    )

    prompt_b = len(args.prompt.encode("utf-8"))
    _print_header(args, base_url, prompt_b)

    if args.start_concurrency < 1:
        print("错误: start-concurrency 须 >= 1", file=sys.stderr)
        sys.exit(2)
    if args.start_concurrency > args.max_concurrency:
        print("错误: start-concurrency 不能大于 max-concurrency", file=sys.stderr)
        sys.exit(2)

    try:
        if args.scheduler == "batch":
            await _async_main_batch(client, args, jsonl_fp)
        else:
            await _async_main_overlap(client, args, jsonl_fp)
    finally:
        await client.close()
        if jsonl_fp:
            jsonl_fp.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "RPM 探针：batch=整波 gather；overlap=重叠发起 + target_cap 爬坡；"
            "记录 t_start/t_end，首次失败锚定前 60s 内发起数。"
        )
    )
    parser.add_argument(
        "--scheduler",
        choices=("batch", "overlap"),
        default="batch",
        help="batch=每轮 gather 结束再下一轮（默认）；overlap=不等待整波即可发起",
    )
    parser.add_argument(
        "--ramp-interval-sec",
        type=float,
        default=4.0,
        metavar="SEC",
        help="overlap：每隔多少秒尝试提高 target_cap（默认 4）",
    )
    parser.add_argument(
        "--payload",
        choices=("minimal", "heavy"),
        default="minimal",
        help="minimal=短 prompt（默认，易触限）；heavy=大正文+摘要指令",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("NEWAPI_BASE_URL", DEFAULT_BASE_URL),
        help="网关 base_url",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("NEWAPI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        help="API Key",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型 id")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        metavar="N",
        help="max_tokens；不设时 heavy 默认 1000，minimal 默认 64",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="仅 payload=minimal",
    )
    parser.add_argument(
        "--input-tokens",
        type=int,
        default=None,
        metavar="N",
        help="仅 payload=heavy（默认 10000）",
    )
    parser.add_argument(
        "--tiktoken-encoding",
        default="cl100k_base",
        help="heavy 所用 tiktoken 编码",
    )
    parser.add_argument(
        "--i-know-expensive",
        action="store_true",
        help="heavy 且 max_concurrency>16 时跳过警告",
    )
    parser.add_argument(
        "--start-concurrency",
        type=int,
        default=256,
        metavar="N",
        help="首轮并行数 / overlap 初始 target_cap（默认 256）",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=256,
        metavar="N",
        help="并发上限（batch 为波次上限；overlap 为 target_cap 上限）",
    )
    parser.add_argument(
        "--scale",
        choices=("double", "linear"),
        default="double",
    )
    parser.add_argument("--linear-step", type=int, default=2, metavar="N")
    parser.add_argument(
        "--max-requests",
        type=int,
        default=4096,
        metavar="N",
        help="总发起次数上限（成功+失败合计；overlap 会预创建等量 task）（默认 4096）",
    )
    parser.add_argument("--jsonl-out", default=None, metavar="PATH")
    args = parser.parse_args()

    if args.scheduler == "overlap" and args.max_requests > 20_000:
        print(
            "警告: overlap 下会预创建 max_requests 个 asyncio 任务，"
            "数值过大可能占用大量内存；建议不超过 20000。",
            file=sys.stderr,
        )

    if not args.api_key:
        print("错误: 未设置 API Key", file=sys.stderr)
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
                "警告: payload=heavy 且 --max-concurrency>16 费用/耗时极高；"
                "可改用 --max-concurrency 16 或传 --i-know-expensive。",
                file=sys.stderr,
            )

    asyncio.run(_async_main(args))


if __name__ == "__main__":
    main()
