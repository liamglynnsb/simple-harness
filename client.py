# The only file that knows how to reach the model: the gateway's address, the key, and which model.
# Everything else in the project just calls make_client() and model_name().
import os
import anthropic
from dotenv import load_dotenv

load_dotenv()  # reads the .env file (next to this file) into os.environ, so no key lives in the code

GATEWAY_BASE_URL = "https://your-gateway.example.com"

def make_client():
    """Build the SDK client that talks to the model through the gateway.

    The SDK insists on an api_key, so we pass a dummy; the gateway ignores it and checks the
    x-gateway-key header instead, which carries the real key from the environment.
    """
    return anthropic.Anthropic(
        api_key="dummy",
        base_url=GATEWAY_BASE_URL,
        default_headers={"x-gateway-key": os.environ["ANTHROPIC_API_KEY"]}
    )

def model_name():
    """Which model to call, from HARNESS_MODEL in .env (switching models is a one-line change)."""
    return os.environ["HARNESS_MODEL"]