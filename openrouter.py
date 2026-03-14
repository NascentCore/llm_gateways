import json
import os

import cyclopts
import requests
from dotenv import load_dotenv

load_dotenv()

app = cyclopts.App()


@app.default
def main(providers: str, output: str = "models.json"):
    """Fetch OpenRouter models filtered by provider.

    Args:
        providers: Comma-separated provider names (e.g. google,anthropic).
        output: Output JSON file path.
    """
    api_key = os.environ["OPENROUTER_API_KEY"]
    provider_list = [p.strip() for p in providers.split(",")]

    resp = requests.get(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    all_models = resp.json()["data"]

    filtered = [
        m for m in all_models
        if any(m["id"].startswith(p + "/") for p in provider_list)
    ]

    with open(output, "w") as f:
        json.dump(filtered, f, indent=2)

    print(f"Wrote {len(filtered)} models to {output}")
    for p in provider_list:
        count = sum(1 for m in filtered if m["id"].startswith(p + "/"))
        print(f"  {p}: {count}")


if __name__ == "__main__":
    app()
