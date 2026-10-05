import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

GATEWAY_BASE_URL = "https://your-gateway.example.com"

def make_client():
    return anthropic.Anthropic(
        api_key="dummy",
        base_url=GATEWAY_BASE_URL,
        default_headers={"x-gateway-key": os.environ["ANTHROPIC_API_KEY"]}
    )

def model_name():
    return os.environ["HARNESS_MODEL"]