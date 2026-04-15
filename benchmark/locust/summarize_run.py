#!/usr/bin/env python3
"""
解析 Locust 导出的 *_stats.csv，在终端输出简短汇总。
用法:
  python summarize_run.py                    # 当前目录下最新的 *_stats.csv
  python summarize_run.py report_stats.csv
  python summarize_run.py report_stats.csv --failures
若同目录存在 locust_last_token_metrics.json（由 locustfile 压测结束写入），会一并打印 RPM/TPM。
依赖: 仅标准库。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

TOKEN_METRICS_NAME = "locust_last_token_metrics.json"


def _f(row: dict[str, str], *keys: str) -> str | None:
    for k in keys:
        if k in row and row[k] != "":
            return row[k]
    lower = {a.lower(): a for a in row}
    for k in keys:
        lk = k.lower()
        if lk in lower:
            return row[lower[lk]]
    return None


def _int(row: dict[str, str], *keys: str) -> int:
    v = _f(row, *keys)
    if v is None:
        return 0
    try:
        return int(float(v))
    except ValueError:
        return 0


def _float(row: dict[str, str], *keys: str) -> float:
    v = _f(row, *keys)
    if v is None:
        return 0.0
    try:
        return float(v)
    except ValueError:
        return 0.0


def find_default_stats_csv(cwd: Path) -> Path | None:
    candidates = sorted(
        cwd.glob("*_stats.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for p in candidates:
        if "stats_history" in p.name:
            continue
        return p
    return None


def print_rpm_tpm_near(stats_path: Path) -> None:
    """读取压测目录下的 locust_last_token_metrics.json（与 locust 运行 cwd 一致时有效）。"""
    for base in (stats_path.parent, Path.cwd()):
        p = base / TOKEN_METRICS_NAME
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        print("RPM / TPM（来自最近一次压测 locustfile 写入的 JSON）")
        print("-" * 56)
        print(f"  文件:        {p.name}")
        print(f"  时长:        {data.get('elapsed_sec', '?')} s")
        print(f"  RPM:         {data.get('rpm_all_requests', '?')}  （全部请求/分钟）")
        print(f"  TPM(total):  {data.get('tpm_total_tokens', '?')}")
        print(f"  TPM(prompt): {data.get('tpm_prompt_tokens', '?')}  |  completion: {data.get('tpm_completion_tokens', '?')}")
        print(f"  Σ tokens:    total={data.get('sum_total_tokens', '?')}  "
              f"(含 usage 响应 {data.get('responses_with_usage', '?')} / 总请求 {data.get('total_requests', '?')})")
        print()
        return
    return


def failures_csv_path(stats_path: Path) -> Path:
    name = stats_path.name
    if name.endswith("_stats.csv"):
        return stats_path.with_name(name[: -len("_stats.csv")] + "_failures.csv")
    return stats_path.with_suffix("").with_name(stats_path.stem + "_failures.csv")


def print_failures(failures_path: Path) -> None:
    if not failures_path.is_file():
        print(f"\n(未找到 {failures_path.name}，跳过失败明细)", file=sys.stderr)
        return
    with failures_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("\n无失败记录。")
        return
    print("\n失败明细 (次数 / Method / Name / 错误摘要)")
    print("-" * 72)
    for row in rows:
        method = _f(row, "Method", "Type") or ""
        name = _f(row, "Name") or ""
        err = _f(row, "Error", "Message") or ""
        occ = _int(row, "Occurrences", "Count")
        short = err.replace("\n", " ")[:100]
        print(f"  {occ:5d}  {method}  {name[:40]}")
        if short:
            print(f"         {short}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize Locust *_stats.csv for terminal output.")
    ap.add_argument(
        "stats_csv",
        nargs="?",
        help="Path to Locust *_stats.csv (default: newest *_stats.csv in cwd)",
    )
    ap.add_argument(
        "--failures",
        action="store_true",
        help="Also print *_failures.csv if present",
    )
    args = ap.parse_args()

    cwd = Path.cwd()
    if args.stats_csv:
        path = Path(args.stats_csv)
        if not path.is_file():
            print(f"文件不存在: {path}", file=sys.stderr)
            return 1
    else:
        found = find_default_stats_csv(cwd)
        if not found:
            print("当前目录下未找到 *_stats.csv，请指定路径或先运行 locust --csv=...", file=sys.stderr)
            return 1
        path = found

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print(f"空文件: {path}", file=sys.stderr)
        return 1

    agg = next((r for r in rows if (_f(r, "Name") or "").strip() == "Aggregated"), None)

    print(f"Locust 结果摘要  ({path.name})")
    print("=" * 56)

    if agg:
        req = _int(agg, "Request Count", "Requests")
        fail = _int(agg, "Failure Count", "Failures")
        rate = (100.0 * fail / req) if req else 0.0
        rps = _float(agg, "Requests/s", "RPS")
        med = _int(agg, "Median Response Time", "50%")
        avg = _float(agg, "Average Response Time", "Avg")
        mx = _int(agg, "Max Response Time", "Max")
        print(f"  总请求:     {req}")
        print(f"  失败:       {fail}  ({rate:.2f}%)")
        print(f"  RPS:        {rps:.2f}")
        print(f"  响应(ms):   中位 {med}  |  平均 {avg:.0f}  |  最大 {mx}")
    else:
        print("  (未找到 Aggregated 行，以下仅列出各端点)")

    print()
    print("分桶 (按 Name)")
    print("-" * 56)

    entries = []
    for row in rows:
        name = (_f(row, "Name") or "").strip()
        if not name or name == "Aggregated":
            continue
        if _int(row, "Request Count") == 0:
            continue
        entries.append(row)

    entries.sort(key=lambda r: (_f(r, "Name") or ""))
    name_w = 42
    if entries:
        name_w = min(48, max(28, max(len(_f(r, "Name") or "") for r in entries)))

    print(f"  {'Name':<{name_w}}  {'reqs':>6}  {'fail':>5}  {'RPS':>6}  {'p50ms':>7}  {'avgms':>7}")
    print("  " + "-" * (name_w + 32))

    for row in entries:
        name = (_f(row, "Name") or "")[:name_w]
        req = _int(row, "Request Count")
        fail = _int(row, "Failure Count")
        rps = _float(row, "Requests/s")
        med = _int(row, "Median Response Time", "50%")
        avg = _float(row, "Average Response Time")
        print(f"  {name:<{name_w}}  {req:>6}  {fail:>5}  {rps:>6.2f}  {med:>7}  {avg:>7.0f}")

    if args.failures:
        print_failures(failures_csv_path(path))

    print_rpm_tpm_near(path)

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
