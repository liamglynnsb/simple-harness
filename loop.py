from client import make_client, model_name
from tools import FUNCTIONS, CALCULATOR


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
        if response.stop_reason == "tool_use":
            for block in response.content:
                if block.type == "tool_use":
                    result = FUNCTIONS[block.name](**block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            messages.append({"role": "user", "content": tool_results})
        elif response.stop_reason == "end_turn":
            return response.content[0].text
        elif response.stop_reason == "max_tokens":
            text_results = ""
            note = "Response stopped; max tokens reached"
            for block in response.content:
                if block.type == "text":
                    text_results += block.text
            if text_results:
                return text_results + "\n" + note
            return note
        else:
            return "Response stopped due to: " + response.stop_reason
    return "Error: Max loops reached"


if __name__ == "__main__":
    client = make_client()
    messages = [{"role": "user", "content": "What is 1234 times 5678?"}]
    print(run_agent(client, messages, [CALCULATOR]))
