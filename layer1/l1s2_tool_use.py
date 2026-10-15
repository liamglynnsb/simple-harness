from client import make_client, model_name

client = make_client()

calculator_tool = {
    "name": "calculator",
    "description": "Do basic arithmetic on two numbers",
    "input_schema": {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["add", "subtract", "multiply", "divide"]},
            "a": {"type": "number"},
            "b": {"type": "number"},
        },
        "required": ["operation", "a", "b"],
    },
}

response = client.messages.create(
    model=model_name(),
    max_tokens=300,
    tools=[calculator_tool],
    messages=[{"role": "user", "content": "What is 1234 times 5678"}],
)

print(response)