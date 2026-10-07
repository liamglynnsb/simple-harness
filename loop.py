from client import make_client, model_name
from tools import FUNCTIONS, CALCULATOR, READ_FILE


def collect_text(response):
    parts = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "\n".join(parts)


def run_agent(client, messages, tools, max_loops=10):
    for _ in range(max_loops):
        tool_results = []
        response = client.messages.create(
            model=model_name(),
            max_tokens=300,
            tools=tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        # print("blocks this pass:", [b.type for b in response.content])
        if response.stop_reason == "tool_use":
            for block in response.content:
                if block.type == "tool_use":
                    # print("calling", block.name, "with input", block.input)
                    result = FUNCTIONS[block.name](**block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            messages.append({"role": "user", "content": tool_results})
        elif response.stop_reason == "end_turn":
            return collect_text(response)
        elif response.stop_reason == "max_tokens":
            note = "Response stopped; max tokens reached"
            text_results = collect_text(response)
            if text_results:
                return text_results + "\n" + note
            return note
        else:
            return "Response stopped due to: " + response.stop_reason
    return "Error: Max loops reached"


if __name__ == "__main__":
    client = make_client()
    messages = [{"role": "user", "content": "Read data/a.txt and data/b.txt, and also tell me what 12 times 12 is."}]
    answer = run_agent(client, messages, [CALCULATOR, READ_FILE])
    print(answer)
    for m in messages:
        print(m["role"], "->", m["content"] if isinstance(m["content"], str) else [getattr(b, "type", None) or b.get("type") for b in m["content"]])