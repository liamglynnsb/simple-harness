from client import make_client, model_name

client = make_client()

first = client.messages.create(
    model=model_name(),
    max_tokens=100,
    messages=[{"role": "user", "content": "My name is Liam"}],
)

print(first.content[0].text)

second = client.messages.create(
    model=model_name(),
    max_tokens=100,
    messages=[{"role": "user", "content": "My name is Liam"}, {"role": "assistant", "content": first.content[0].text}, {"role": "user", "content": "What is my name?"}],
)

print(second.content[0].text)