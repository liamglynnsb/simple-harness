# The harness side of MCP over stdio (protocol revision 2026-07-28): start a server as a subprocess, talk to it
# through its stdin and stdout, and turn its tools into things the loop already knows how to use.
#
# This does by code what you did by hand in 5b: write one JSON line to the server's stdin, read one line back.
import json
import subprocess
import sys

PROTOCOL_VERSION = "2026-07-28"
META = {
    "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
    "io.modelcontextprotocol/clientCapabilities": {},
}


class McpError(Exception):
    """The server answered with a JSON-RPC error, or it stopped answering."""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class McpToolError(Exception):
    """The server's tool ran and failed (the reply said isError). The message is the tool's own explanation,
    written for the model, so it can correct itself. Separate from McpError, which is about the protocol or the
    connection."""


class McpClient:
    """One running server. Use it with `with`, so the server is always shut down cleanly:

        with McpClient([sys.executable, "mcp_server.py"]) as client:
            tools = client.list_tools()
    """

    def __init__(self, command):
        # The harness holds the other ends of the pipes: what we write to .stdin arrives on the server's stdin,
        # and what the server prints on its stdout is what we read from .stdout. The terminal is not involved.
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self._next_id = 1

    def request(self, method, **params):
        """Send one request and return its `result`. Raises McpError if the server replies with an error."""
        message = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": {**params, "_meta": META}}
        self._next_id += 1
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()  # push the line out now; otherwise it can sit in a buffer and the server never sees it
        line = self.process.stdout.readline()
        if line == "":  # end of file: the server closed its output, or died
            raise McpError("the server stopped answering (it closed its output)")
        reply = json.loads(line)
        if "error" in reply:
            raise McpError(reply["error"]["message"], reply["error"]["code"])
        return reply["result"]

    def list_tools(self):
        return self.request("tools/list")["tools"]

    def call_tool(self, name, arguments):
        return self.request("tools/call", name=name, arguments=arguments)

    def close(self):
        """Shut down the way the spec says: close the server's input, wait for it to exit, force-stop it if it won't."""
        self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


def to_tool_definition(mcp_tool):
    """An MCP tool definition (inputSchema) as the model API expects it (input_schema)."""
    return {
        "name": mcp_tool["name"],
        "description": mcp_tool.get("description", ""),
        "input_schema": mcp_tool["inputSchema"],
    }


def make_tool_function(client, tool_name):
    """Make the function to store in FUNCTIONS for one MCP tool, so the loop can call it like any other:
    FUNCTIONS[name](**input). It sends a tools/call request and returns the result text.

    This is a closure: the function built here remembers `client` and `tool_name` from when it was made.
    """

    def call(**arguments):
        result = client.call_tool(tool_name, arguments)
        text = "\n".join(item["text"] for item in result["content"] if item.get("type") == "text")
        if result.get("isError"):
            raise McpToolError(text)  # a tool function that fails raises; execute_tool already turns that into a flagged error
        return text

    call.__name__ = tool_name
    return call


def register_tools(client, functions):
    """Ask the server what tools it has, add one wrapper function per tool to `functions` (the loop's FUNCTIONS
    table), and return the tools' definitions in the model API format, ready to put in the `tools` list.

    After this, the loop treats the server's tools like any other: the model sees them in `tools`, and
    FUNCTIONS[name](**input) calls the wrapper. Nothing in loop.py changes.
    """
    definitions = []
    for mcp_tool in client.list_tools():
        functions[mcp_tool["name"]] = make_tool_function(client, mcp_tool["name"])
        definitions.append(to_tool_definition(mcp_tool))
    return definitions

