import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
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

if result.get("choices"):
    message = result["choices"][0]["message"]
    if message.get("images"):
        for image in message["images"]:
            image_url = image["image_url"]["url"]
            print(f"Generated image: {image_url[:50]}...")
