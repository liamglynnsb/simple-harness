from client import make_client, model_name

client = make_client()

questions = [
    "My name is Liam.",
    "What is the capital of France?",
    "What is that city known for?",
    "Name one famous museum there.",
    "Who painted its most famous work?",
    "What is my name?",
]

messages = []

for turn, question in enumerate(questions, start=1):
    messages.append({"role": "user", "content": question})
    response = client.messages.create(
        model=model_name(),
        max_tokens=300,
        messages=messages,
    )
    reply = response.content[0].text
    messages.append({"role": "assistant", "content": reply})
    print(
        f"turn {turn}: "
        f"input_tokens={response.usage.input_tokens} "
        f"output_tokens={response.usage.output_tokens}"
    )
