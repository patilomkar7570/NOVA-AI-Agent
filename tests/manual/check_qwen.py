from ollama import chat

response = chat(
    model="qwen3:8b",
    messages=[
        {
            "role": "user",
            "content": "Say hello and tell me in one sentence what you can do."
        }
    ],
    think=False
)

print(response.message.content)