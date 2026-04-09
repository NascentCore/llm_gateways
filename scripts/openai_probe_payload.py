"""
OpenAI 兼容 chat 探针共用的用户正文构造（heavy：tiktoken 定长「书籍节选 + 摘要」）。

供 rpm_until_limit、rpm_minute_window_probe 等脚本导入；勿将 API Key 写入本模块。
"""

from __future__ import annotations

import sys

import tiktoken

DEFAULT_PROMPT = "Reply with exactly: OK"

BOOK_PREFIX = """以下为长篇小说《虚拟探针纪事》的连续节选（同一部作品，多段拼接，语体统一）。请你通读全部正文。
然后撰写一份尽可能详细的中文读书总结，至少包含：主要情节发展、重要人物与关系、冲突与转折、叙事视角与语言风格、主题与隐喻、你认为值得讨论的细节。请分小节书写，篇幅尽量长，直至被输出上限截断为止。

==================== 正文节选 ====================

"""


def build_heavy_user_content(input_tokens: int, encoding_name: str) -> str:
    """在指定 tiktoken 编码下构造恰好 input_tokens 个 token 的用户正文（prefix + 填充）。"""
    if input_tokens < 1:
        return ""
    enc = tiktoken.get_encoding(encoding_name)
    prefix_ids = enc.encode(BOOK_PREFIX)
    if len(prefix_ids) >= input_tokens:
        ids = prefix_ids[:input_tokens]
    else:
        rest = input_tokens - len(prefix_ids)
        filler = " The quick brown fox jumps over the lazy dog."
        fill_ids: list[int] = []
        while len(fill_ids) < rest:
            fill_ids.extend(enc.encode(filler))
        ids = prefix_ids + fill_ids[:rest]
    text = enc.decode(ids)
    actual = len(enc.encode(text))
    if actual != input_tokens:
        print(
            f"错误: heavy 正文在「{encoding_name}」下为 {actual} tokens，目标 {input_tokens}",
            file=sys.stderr,
        )
        sys.exit(3)
    return text
