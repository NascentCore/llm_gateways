"""
Invoke Gemini 3.1 Pro (high-thinking) with a ~200k token prompt to approximate
maximum LLM invocation latency. Uses python-dotenv for env vars and Google GenAI SDK.
"""

import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from long_prompt_generator import build_prompt

# Load .env (GEMINI_API_KEY or GOOGLE_API_KEY)
load_dotenv()

MODEL = "gemini-3.1-pro-preview"
TARGET_PROMPT_TOKENS = 200_000


def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit(
            "Set GEMINI_API_KEY or GOOGLE_API_KEY in .env or environment."
        )

    client = genai.Client(api_key=api_key)

    print("Building ~200k token prompt (complex reasoning tasks)...")
    prompt = build_prompt()
    char_count = len(prompt)
    print(f"Prompt length: {char_count:,} characters (≈{char_count // 4:,} tokens)")

    # Optional: count tokens via API (may use a different model for counting)
    try:
        count_resp = client.models.count_tokens(model=MODEL, contents=prompt)
        if hasattr(count_resp, "total_tokens") and count_resp.total_tokens:
            print(f"API token count: {count_resp.total_tokens:,}")
    except Exception as e:
        print(f"Token count skipped: {e}")

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="high"),
        max_output_tokens=8192,
    )

    print(f"Calling {MODEL} with thinking_level=high...")
    start = time.perf_counter()
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=config,
    )
    elapsed = time.perf_counter() - start

    print(f"Latency (wall-clock): {elapsed:.2f}s")
    if getattr(response, "usage_metadata", None):
        um = response.usage_metadata
        print(
            f"Usage: prompt_tokens={getattr(um, 'prompt_token_count', 'N/A')}, "
            f"output_tokens={getattr(um, 'candidates_token_count', 'N/A')}, "
            f"thoughts_tokens={getattr(um, 'thoughts_token_count', 'N/A')}"
        )
    if response.text:
        print(f"Response length: {len(response.text)} chars (first 500):")
        print(response.text[:500] + "..." if len(response.text) > 500 else response.text)
    else:
        print("(No text in response; check candidates/parts.)")


if __name__ == "__main__":
    main()
