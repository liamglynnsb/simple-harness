# The harness side of MCP over stdio (protocol revision 2026-07-28): start a server as a subprocess, talk to it
# through its stdin and stdout, and turn its tools into things the loop already knows how to use.
#
# This does by code what you did by hand in 5b: write one JSON line to the server's stdin, read one line back.
import json
import queue
import subprocess
import sys
import threading

PROTOCOL_VERSION = "2026-07-28"
META = {
    "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
    "io.modelcontextprotocol/clientCapabilities": {},
}


class McpError(Exception):
    """The server answered with a JSON-RPC error (a protocol problem: retrying can't change it)."""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class McpTransportError(McpError):
    """The connection failed: the server died, stopped answering, or sent something that isn't a valid reply.
    These are the failures that restarting the server and trying again can fix."""


class McpToolError(Exception):
    """The server's tool ran and failed (the reply said isError). The message is the tool's own explanation,
    written for the model, so it can correct itself. Separate from McpError, which is about the protocol or the
    connection."""


def _read_lines(process, lines):
    """Runs in a helper thread: copy every line the server prints into a queue, then a None when its output ends.
    A thread is needed because reading a pipe waits forever; with a queue the main thread can wait with a time limit."""
    for line in process.stdout:
        lines.put(line)
    lines.put(None)


class McpClient:
    """One running server. Use it with `with`, so the server is always shut down cleanly:

        with McpClient([sys.executable, "mcp_server.py"], timeout=10, retries=1) as client:
            tools = client.list_tools()

    timeout: seconds to wait for each reply before deciding the server is stuck.
    retries: how many times to restart the server and send the request again after a connection failure. Only safe
             for tools that are safe to repeat (like counting letters); a tool with side effects could act twice.
    """

    def __init__(self, command, timeout=10, retries=1):
        self.command, self.timeout, self.retries = command, timeout, retries
        self._next_id = 1
        self._lock = threading.Lock()  # one pipe: two requests at once would interleave their lines, so take turns
        self._start()

    def _start(self):
        # The harness holds the other ends of the pipes: what we write to .stdin arrives on the server's stdin,
        # and what the server prints on its stdout arrives in self._lines. The terminal is not involved.
        self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self._lines = queue.Queue()
        threading.Thread(target=_read_lines, args=(self.process, self._lines), daemon=True).start()

    def _restart(self):
        """Throw the server away and start a fresh one. A stuck server may still reply late, and that reply would be
        read as the answer to the next request, so the old process (and its queue) must go. The protocol is stateless,
        so the new server needs nothing from the old one."""
        self.process.kill()
        self.process.wait()
        self._start()

    def _request_once(self, method, params):
        """Send one request on the current connection and return its result. Connection failures raise McpTransportError."""
        message = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": {**params, "_meta": META}}
        self._next_id += 1
        try:
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()  # push the line out now; otherwise it can sit in a buffer and the server never sees it
        except (BrokenPipeError, ValueError):  # the server is gone (ValueError: its input was already closed)
            raise McpTransportError("the tool server is not running")
        try:
            line = self._lines.get(timeout=self.timeout)
        except queue.Empty:
            raise McpTransportError("the tool server did not answer within " + str(self.timeout) + " seconds")
        if line is None:  # the server closed its output, or died
            raise McpTransportError("the tool server stopped answering (it closed its output)")
        try:
            reply = json.loads(line)
        except json.JSONDecodeError:
            raise McpTransportError("the tool server sent something that is not valid JSON")
        if reply.get("id") != message["id"]:
            raise McpTransportError("the tool server's reply did not match the request")
        if "error" in reply:  # a protocol error: the server is fine, the request was not. Retrying would not help.
            raise McpError(reply["error"]["message"], reply["error"]["code"])
        return reply["result"]

    def request(self, method, **params):
        """Send a request and return its `result`. If the connection fails, restart the server and try again, up to
        `retries` more times; then raise one clear McpTransportError. A JSON-RPC error (McpError) is raised at once."""
        attempts = self.retries + 1
        with self._lock:  # threads may call this at the same time (parallel tools); the pipe handles one request at a time
            for attempt in range(1, attempts + 1):
                try:
                    return self._request_once(method, params)
                except McpTransportError as problem:
                    print("MCP SERVER PROBLEM (attempt " + str(attempt) + " of " + str(attempts) + "):", problem, file=sys.stderr)
                    if attempt == attempts:
                        raise McpTransportError(str(problem) + " (tried " + str(attempts) + " time" + ("s" if attempts > 1 else "") + ")")
                    self._restart()

    def list_tools(self):
        return self.request("tools/list")["tools"]

    def call_tool(self, name, arguments):
        return self.request("tools/call", name=name, arguments=arguments)

    def close(self):
        """Shut down the way the spec says: close the server's input, wait for it to exit, force-stop it if it won't."""
        try:
            self.process.stdin.close()
        except BrokenPipeError:
            pass  # the server already died: the unsent bytes have nowhere to go, and there is nothing left to shut down
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


def register_tools_or_ask(client, functions, ask=input):
    """Like register_tools, but if the server can't be used (dead, silent, garbage), tell the user and let THEM decide:
    carry on with only the local tools (returns an empty list), or stop (the original error is raised).

    `ask` is the function that asks the question and returns the answer; it defaults to input() (the keyboard) and a
    test can pass a fake one instead.
    """
    try:
        return register_tools(client, functions)
    except McpError as problem:
        print("The tool server could not be used:", problem)
        if ask("Continue with only the local tools? [y/N] ").strip().lower() == "y":
            return []
        raise

