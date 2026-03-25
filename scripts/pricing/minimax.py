import anthropic

client = anthropic.Anthropic()


model = "dg/MiniMax-M2.7"

response = client.messages.create(
    model=model,
    max_tokens=1000,
    system=[
        {"type": "text", "text": "You are a helpful assistant."},
        {
            "type": "text",
            "text": "<the entire content of 'Pride and Prejudice' by Jane Austen>",
            "cache_control": {"type": "ephemeral"},
        },
    ],
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Analyze the book 'Pride and Prejudice' by Jane Austen.",
                }
            ],
        }
    ],
)

print(response.usage.model_dump_json())


# for block in response.content:
#     if block.type == "thinking":
#         print(block.thinking)
#     elif block.type == "text":
#         print(block.text)


response = client.messages.create(
    model=model,
    max_tokens=1000,
    system=[
        {"type": "text", "text": "You are a helpful assistant."},
        {
            "type": "text",
            "text": "<the entire content of 'Pride and Prejudice' by Jane Austen>",
            "cache_control": {"type": "ephemeral"},
        },
    ],
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Analyze the book 'Pride and Prejudice' by Jane Austen.",
                }
            ],
        }
    ],
)

print(response.usage.model_dump_json())
