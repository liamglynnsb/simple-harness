# The only file that knows how to reach the model: the key, an optional gateway address and headers,
# and which model. Everything else in the project just calls make_client() and model_name().
import json
import os
import anthropic
from dotenv import load_dotenv

load_dotenv()  # reads the .env file (next to this file) into os.environ, so no key lives in the code


def make_client():
    """Build the SDK client. Everything comes from the environment (see .env.example):

    ANTHROPIC_API_KEY      the key (the SDK reads this itself)
    ANTHROPIC_BASE_URL     optional: the address of a gateway, if your calls go through one (the SDK reads this too)
    HARNESS_EXTRA_HEADERS  optional: a JSON object of extra headers, for a gateway that wants its own key or labels
    """
    extra_headers = json.loads(os.environ.get("HARNESS_EXTRA_HEADERS", "{}"))
    return anthropic.Anthropic(default_headers=extra_headers)


def model_name():
    """Which model to call, from HARNESS_MODEL in .env (switching models is a one-line change)."""
    return os.environ["HARNESS_MODEL"]
