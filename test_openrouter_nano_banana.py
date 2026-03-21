import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("OPENROUTER_API_KEY")
if not api_key:
    print(
        "Error: OPENROUTER_API_KEY is not set. "
        "Export it or add it to .env (same as for openrouter.py; see AGENTS.md).",
        file=sys.stderr,
    )
    sys.exit(1)

response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    data=json.dumps(
        {
            "model": "google/gemini-3.1-flash-image-preview",
            "messages": [
                {
                    "role": "user",
                    "content": "Generate a beautiful sunset over mountains",
                }
            ],
            "modalities": ["image", "text"],
        }
    ),
)

result = response.json()
print(result)

choices = result.get("choices")
if isinstance(choices, list) and len(choices) > 0:
    message = choices[0].get("message") or {}
    for image in message.get("images") or []:
        if not isinstance(image, dict):
            continue
        url_obj = image.get("image_url")
        url = url_obj.get("url") if isinstance(url_obj, dict) else None
        if url:
            print(f"Generated image: {url[:50]}...")
