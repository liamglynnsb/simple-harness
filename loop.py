from client import make_client, model_name
from tools import FUNCTIONS, CALCULATOR

client = make_client()

messages = [{"role": "user", "content": "What is 1234 times 5678?"}]

def run_agent(client, messages, tools):
    while True:
        tool_results = []
        response = client.messages.create(
            model=model_name(),
            max_tokens=300,
            tools=tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        if(response.stop_reason == "tool_use"):
            for block in response.content:
                if block.type == "tool_use":
                    result = FUNCTIONS[block.name](**block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            messages.append({"role": "user", "content": tool_results})
        elif(response.stop_reason == "end_turn"):
            return response.content[0].text
        else:
            return "Error: " + response.stop_reason

print(run_agent(client,messages,[CALCULATOR]))