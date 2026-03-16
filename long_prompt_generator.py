"""
Generate a ~200k token prompt designed to trigger maximum reasoning latency.
Uses multi-step math, logic, and analysis tasks to force deep chain-of-thought.
"""

import random
from typing import Iterator

# Target: ~200_000 tokens. Approximate 1 token ≈ 4 chars for English.
TARGET_CHARS = 200_000 * 4  # 800_000


def _math_problems(n: int) -> Iterator[str]:
    """Yield n multi-step algebra/number-theory style problems."""
    for i in range(n):
        a, b, c = random.randint(2, 50), random.randint(2, 50), random.randint(1, 100)
        d = a * b + c
        yield (
            f"Problem {i+1}: Find all positive integers x such that "
            f"{a}*x^2 + {b}*x + {c} = {d}. "
            "Show every algebraic step, then list all solutions and verify each one. "
            "Finally state the number of distinct solutions.\n\n"
        )


def _logic_puzzles(n: int) -> Iterator[str]:
    """Yield n logic puzzles requiring careful deduction."""
    templates = [
        "In a row of five people A,B,C,D,E, A is not next to B, C is left of D, E is at an end. List all valid orderings and prove there are no others.\n\n",
        "Three boxes: one has two gold coins, one two silver, one one of each. You pick one coin from one box and it is gold. What is the probability the other coin in that box is gold? Derive step by step using conditional probability.\n\n",
        "Five suspects. Exactly three lie. Alice says Bob lied; Bob says Carol lied; Carol says Dave lied; Dave says Eve lied; Eve says Alice lied. Who lied? Enumerate possibilities and eliminate.\n\n",
    ]
    for i in range(n):
        yield f"Logic puzzle {i+1}: " + templates[i % len(templates)]


def _code_trace_tasks(n: int) -> Iterator[str]:
    """Yield n code-trace tasks."""
    for i in range(n):
        k = random.randint(3, 12)
        yield (
            f"Trace {i+1}: Let f(0)=0, f(1)=1, and f(n)=f(n-1)+2*f(n-2) for n>=2. "
            f"Compute f({k}) by hand step by step (list f(0), f(1), ..., f({k})), then give the final value.\n\n"
        )


def _analysis_blocks(n: int, chars_per_block: int) -> Iterator[str]:
    """Yield n blocks of synthetic text to analyze (to pad token count and add analysis load)."""
    words = (
        "consider hypothesis evidence therefore conclude argument premise "
        "assumption inference validity constraint optimization equilibrium "
        "distribution variance correlation causality bias regression "
        "algorithm complexity recursion induction proof lemma theorem "
        "formal verify derive contradiction necessary sufficient "
    ).split()
    for b in range(n):
        block = []
        while len(" ".join(block)) < chars_per_block:
            block.append(random.choice(words))
        text = " ".join(block)
        yield (
            f"Section {b+1} (analyze and summarize in one paragraph, "
            "then list three possible implications):\n" + text + "\n\n"
        )


def build_prompt(target_chars: int = TARGET_CHARS) -> str:
    """
    Build a single prompt string of approximately target_chars characters,
    designed to trigger long reasoning (multi-step math, logic, code trace, analysis).
    """
    header = (
        "You are a rigorous reasoner. Your task is to solve EVERY item below in order. "
        "For each item: (1) Show your reasoning step by step. (2) Justify every deduction. "
        "(3) Give a final short answer. Do not skip any item. "
        "Work through them sequentially; later items do not depend on earlier answers. "
        "Begin with the first item.\n\n"
        "---\n\n"
    )

    out: list[str] = [header]
    n_chars = len(header)

    # Mix of problem types to keep reasoning diverse and heavy (~800k chars total)
    n_math = 1200
    n_logic = 800
    n_code = 800
    n_analysis_blocks = 150
    chars_per_analysis_block = 2000

    for s in _math_problems(n_math):
        if n_chars >= target_chars:
            break
        out.append(s)
        n_chars += len(s)

    for s in _logic_puzzles(n_logic):
        if n_chars >= target_chars:
            break
        out.append(s)
        n_chars += len(s)

    for s in _code_trace_tasks(n_code):
        if n_chars >= target_chars:
            break
        out.append(s)
        n_chars += len(s)

    for s in _analysis_blocks(n_analysis_blocks, chars_per_analysis_block):
        if n_chars >= target_chars:
            break
        out.append(s)
        n_chars += len(s)

    return "".join(out)
