from client import make_client, model_name
from tools import CALCULATOR, READ_FILE

client = make_client()

# response 1: use tools

messages1 = [{"role": "user", "content": "Say hello in 5 words"}]

response1 = client.messages.create(
    model=model_name(),
    max_tokens=1000,
    tools=[CALCULATOR, READ_FILE],
    messages=messages1,
)

print(f"Tools: input = {response1.usage.input_tokens}, output = {response1.usage.output_tokens}")

# response 2: no tools

messages2 = [{"role": "user", "content": "Say hello in 5 words"}]

response2 = client.messages.create(
    model=model_name(),
    max_tokens=1000,
    messages=messages2,
)

print(f"No Tools: input = {response2.usage.input_tokens}, output = {response2.usage.output_tokens}")

print(f"Difference: {response1.usage.input_tokens - response2.usage.input_tokens} tokens")