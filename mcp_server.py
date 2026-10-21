# A minimal MCP server over stdio (protocol revision 2026-07-28), with one tool.
#
# How it talks: the client writes one JSON-RPC message per line to this program's stdin, and this program writes
# one message per line to its stdout. stdout carries ONLY protocol messages; anything else (logs) goes to stderr.
# It keeps no memory between requests: every request carries its own protocol version and capabilities in `_meta`.
#
# Run it by hand:   .venv/bin/python mcp_server.py      then type a JSON line and press Enter.
# Stop it:          press Ctrl-D (closes its stdin; the server exits when its input ends).
import json
import sys

PROTOCOL_VERSION = "2026-07-28"

# ---------------------------------------------------------------------------------------------------------
# YOU WRITE THIS: what the model reads about the tool. Fill in the three fields below.
#   name         a short identifier (letters, digits, underscore)
#   description  what it does and when to use it, written for a model that has never seen this project
#                (it counts letters ignoring upper/lower case; say so)
#   inputSchema  a JSON Schema: an object with the properties the function takes, and which are required
#                (the function takes `word` and `letter`, both text)
TOOL = {
    "name": "count_letters",
    "description": "Count the number of times a letter appears in a word, ignoring upper/lower case.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "word": {"type": "string"},
            "letter": {"type": "string", "description": "The letter to count, as a single character"},
        },
        "required": ["word", "letter"],
    },
}
# ---------------------------------------------------------------------------------------------------------


def count_letters(word, letter):
    """The real tool: how many times `letter` appears in `word`, ignoring upper/lower case."""
    if not isinstance(word, str) or not isinstance(letter, str):
        raise ValueError("word and letter must both be text")
    if len(letter) != 1:
        raise ValueError("letter must be a single character, got: " + repr(letter))
    return word.lower().count(letter.lower())


class RpcError(Exception):
    """A protocol-level failure: becomes a JSON-RPC error response (code and message)."""

    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


def check_meta(params):
    """Every request must carry its protocol version and client capabilities in params._meta."""
    meta = params.get("_meta") or {}
    version = meta.get("io.modelcontextprotocol/protocolVersion")
    if version is None or "io.modelcontextprotocol/clientCapabilities" not in meta:
        raise RpcError(-32602, "Missing required _meta field: protocolVersion and clientCapabilities are required")
    if version != PROTOCOL_VERSION:
        raise RpcError(-32022, "Unsupported protocol version",
                       {"supported": [PROTOCOL_VERSION], "requested": version})


def handle(method, params):
    """Return the `result` object for a request, or raise RpcError."""
    check_meta(params)
    if method == "server/discover":
        return {
            "resultType": "complete",
            "supportedVersions": [PROTOCOL_VERSION],
            "capabilities": {"tools": {}},
            "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "letter-counter", "version": "0.1.0"}},
        }
    if method == "tools/list":
        return {"resultType": "complete", "tools": [TOOL]}
    if method == "tools/call":
        if params.get("name") != TOOL["name"]:
            raise RpcError(-32602, "Unknown tool: " + str(params.get("name")))
        try:
            answer = count_letters(**(params.get("arguments") or {}))
            return {"resultType": "complete", "content": [{"type": "text", "text": str(answer)}], "isError": False}
        except Exception as e:  # the tool ran and failed: a normal result flagged isError, so the model can retry
            return {"resultType": "complete", "content": [{"type": "text", "text": str(e)}], "isError": True}
    raise RpcError(-32601, "Method not found: " + str(method))


def send(message):
    print(json.dumps(message), flush=True)  # flush: otherwise the reply can sit in a buffer and never arrive


def main():
    if not TOOL["name"] or not TOOL["description"] or not TOOL["inputSchema"]:
        print("Fill in TOOL (name, description, inputSchema) at the top of mcp_server.py first.", file=sys.stderr)
        sys.exit(1)
    for line in sys.stdin:  # ends when stdin is closed
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            send({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}})
            continue
        if "id" not in request:  # a notification: one-way, so it gets no reply
            print("ignored notification:", request.get("method"), file=sys.stderr)
            continue
        try:
            result = handle(request.get("method"), request.get("params") or {})
            send({"jsonrpc": "2.0", "id": request["id"], "result": result})
        except RpcError as e:
            error = {"code": e.code, "message": e.message}
            if e.data is not None:
                error["data"] = e.data
            send({"jsonrpc": "2.0", "id": request["id"], "error": error})


if __name__ == "__main__":
    main()
