from client import make_client, model_name
from tools import CALCULATOR, calculator

client = make_client()

messages = [{"role": "user", "content": "What is 1234 times 5678?"}]

response = client.messages.create(
    model=model_name(),
    max_tokens=300,
    tools=[CALCULATOR],
    messages=messages,
)

messages.append({"role": "assistant", "content": response.content})

tool_results = []
for block in response.content:
    if block.type == "tool_use":
        result = calculator(**block.input)
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": str(result),
        })

messages.append({"role": "user", "content": tool_results})

final = client.messages.create(
    model=model_name(),
    max_tokens=300,
    tools=[CALCULATOR],
    messages=messages,
)

print(final.stop_reason)
print(final.content[0].text)