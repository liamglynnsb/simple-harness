# Anthropic SDK reference: the data structures we use

A map of the objects, dicts and lists that pass between my code and the model, and how they connect
(for example, how `usage` relates to the text blocks). It is a companion to the learnings, not a
replacement for Anthropic's docs. The facts here were checked against the installed SDK (`anthropic`
1.11.0). The field tables in the appendix are **generated from the SDK itself**, and
`scripts/gen_sdk_reference.py --check` asserts the specific claims in the text, so an SDK upgrade that
changes one of them is caught. Index: [../LEARNINGS.md](../LEARNINGS.md); terms: [glossary.md](glossary.md).

**Where to start.** Read sections 1 to 3 in order: the picture, how to read it, and one full example.
Sections 4 and 5 are look-up material for the request and the reply. Section 6 says where each piece
is in my code.

## 1. The big picture

```
 WHAT I SEND (plain dicts and lists)               WHAT COMES BACK (SDK objects, read with a dot)

 client.messages.create(                           Message
     model=...,                 required              |- id, type, role, model
     max_tokens=...,            required              |- stop_reason      "end_turn" | "tool_use" | "max_tokens" | ...
     messages=[MessageParam,...], required            |- content          a LIST of blocks, in order:
     tools=[ToolParam, ...],      optional            |      TextBlock | ThinkingBlock | ToolUseBlock | ...
     system=..., tool_choice=..., optional            \- usage            ONE Usage per reply (not per block)
     thinking=...)                                           |- input_tokens
        --------------------------------------->             |- output_tokens   (all blocks together)
                                                             \- output_tokens_details.thinking_tokens
```

In the loop the two meet. After each reply I append `response.content`, a list of *objects*, straight
into the next request's `messages`, next to dicts I built myself. The SDK accepts both. (That's also
why a fake reply in a test is a `SimpleNamespace`: it only has to look like the object.)

## 2. How to read the shapes

Everything here is one of three things, and the thing decides how I read inside it:

| it is a... | example | read inside it with | how |
|---|---|---|---|
| **object** | a reply, a block, a `SimpleNamespace` | a dot | `block.name` |
| **dict** | a message I build, a `tool_result` | square brackets and a key | `message["content"]` |
| **list** | `messages`, `response.content` | square brackets and a position (from 0) | `messages[2]` |

**What I send is dicts and lists; what comes back is objects.** That's why the loop mixes dots and
brackets: `block.id` is read from an object the SDK returned, and `"tool_use_id"` is a key in a dict I built.

**Read a path one step at a time, asking "what is this?" before each step.** A `TypeError: list indices
must be integers` means I indexed a list with a string key, so a `[0]` is missing. A `KeyError` means
the dict has no such key (for example `"is_error"` is written only when a tool fails, so on success
test `"is_error" not in the_dict` and don't read it).

**The word `content` appears at three levels and means something different at each:**

```
response.content                 the REPLY's content: a list of blocks (objects)
messages[i]["content"]           a MESSAGE's content: a string, or a list of blocks (what I send)
tool_result_dict["content"]      a TOOL RESULT's content: a string, the tool's output
```

## 3. One complete example: "What is 12 times 12?"

This is the `messages` list at the end of a run with one tool call. The left column says what each
piece is and who made it; the right column is the path that reads it, starting from `messages`.

```
messages                                   list, 4 items; I made it, the loop appended to it
|
|- [0]  dict                               I built this
|        |- "role"     "user"
|        \- "content"  "What is 12 times 12?"            a STRING: plain text
|
|- [1]  dict                               the loop built this around the model's reply
|        |- "role"     "assistant"
|        \- "content"  [ ... ]                           a LIST of OBJECTS: response.content, unchanged
|              |- [0]  ThinkingBlock                     messages[1]["content"][0].type   "thinking"
|              \- [1]  ToolUseBlock                      messages[1]["content"][1]
|                       |- type   "tool_use"
|                       |- id     "toolu_01..."          <- the id the result must carry back
|                       |- name   "calculator"           key into FUNCTIONS
|                       \- input  {"operation": "multiply", "a": 12, "b": 12}   dict: calculator(**input)
|
|- [2]  dict                               the loop built this after running the tool
|        |- "role"     "user"
|        \- "content"  [ ... ]                           a LIST of DICTS: tool_results
|              \- [0]  dict                              messages[2]["content"][0]
|                       |- "type"         "tool_result"
|                       |- "tool_use_id"  "toolu_01..."  same string as the ToolUseBlock's id
|                       \- "content"       "144"         a STRING: the tool's output
|                                                         (no "is_error" key: the call succeeded)
|
\- [3]  dict                               the final reply, appended before the loop returns its text
         |- "role"     "assistant"
         \- "content"  [ TextBlock(text="12 times 12 is 144") ]
```

What to take from it:

- **Roles alternate:** user, assistant, user, assistant. A run with one tool call ends with four messages.
  The loop appends `response.content` on every pass, whatever the `stop_reason`, so the final reply
  (`end_turn`) is appended too, before the text is returned.
- **A `tool_result` is a block, so it goes in a list.** One assistant reply can request several tools,
  and every request needs its own result in the *next* user message, so the loop collects the results
  in a list (`tool_results = []` in `loop.py`) and sends the list as that one message's `content`. With
  one tool call the list has one item. It is still a list.
- **The id links request to result.** Every `tool_use` block needs a `tool_result` with its `id` in the
  next message, or the API rejects the request (Layer 1 Step 4d).
- **A test reads exactly this.** After `run_agent(client, messages, tools)` returns, the test's own
  `messages` list has grown to this shape, because the loop appends to the same list it was passed
  (lists are passed by reference, not copied). The `FakeClient` doesn't touch `messages`; it only logs
  each call's arguments in `client.calls` and hands back the next scripted reply.

## 4. Reference: what I send

`messages.create(...)` has **three required parameters**: `model`, `max_tokens` and `messages`.
Everything else is optional, including `tools`, `system`, `tool_choice` and `thinking`. In this SDK
version the signature has no `temperature`, `top_p` or `top_k`.

My real call is in `run_agent` (`loop.py`):

```
response = client.messages.create(
    model=model_name(),         <- the model slug from HARNESS_MODEL (client.py)
    max_tokens=max_tokens,      <- run_agent's parameter: the limit on one reply
    tools=tools,                <- run_agent's parameter: the list of tool DEFINITIONS (ToolParam dicts)
    messages=messages,          <- run_agent's parameter: THE CONVERSATION, a list of message dicts
)
```

The `role`/`content` dicts are never arguments of `create` themselves. They are the *items* of the list
passed as `messages=`. Each pass sends the whole list again, longer by what the loop appended (the API
remembers nothing between calls, Layer 1 Step 1).

### One message (`MessageParam`)

A dict with exactly two required keys: `role` (who is speaking) and `content` (what they said).

- `role` is `"user"` or `"assistant"` and nothing else. `"user"` is me: my question and the tool results I
  send back. `"assistant"` is the model: its earlier replies, which I send back unchanged. The system
  prompt is **not** a message; it goes in the separate `system` argument.
- `content` is a **string** or a **list of blocks**:

| what I'm sending | `content` is | why |
|---|---|---|
| one plain question | a string | one piece of text; the API treats it as shorthand for `[{"type": "text", "text": "..."}]` |
| tool results | a list of `tool_result` dicts | each carries a `tool_use_id`, so it must be a block |
| text plus a tool result, or several texts | a list | more than one block |
| an image or a document | a list | each is its own block type |
| a block with settings (prompt caching, Layer 5) | a list | the setting sits on the block |

The assistant's turns are always lists, because I append `response.content` as it came back; I never
choose that form. `system` follows the same rule as a user message: a string, or a list of text blocks
when a block needs settings.

### Required keys of each piece

| structure | required keys | notes |
|---|---|---|
| `MessageParam` | `role`, `content` | as above |
| `ToolParam` (a tool definition) | `name`, `input_schema` | `description` is *optional in the SDK*, but the model relies on it, so always write one |
| `ToolResultBlockParam` | `tool_use_id`, `type` | `content` and `is_error` are optional; `tool_use_id` must match the request's `id` |
| `TextBlockParam` | `text`, `type` | a text block when `content` is a list |
| `ToolUseBlockParam` | `id`, `input`, `name`, `type` | what a tool request looks like as input; the SDK also accepts the `ToolUseBlock` object itself |

### A tool definition

A `ToolParam` is a dict that nests a JSON Schema; this is `CALCULATOR` in `tools.py`:

```
ToolParam  (dict)
|- name         "calculator"
|- description  "Do basic arithmetic on two numbers"
\- input_schema  (dict, a JSON Schema)
      |- type  "object"
      |- properties
      |     |- operation   {"type": "string", "enum": ["add", ...]}
      |     |- a           {"type": "number"}
      |     \- b           {"type": "number"}
      \- required   ["operation", "a", "b"]
```

The model's `input` must fit `properties`, and the function's parameter names must match them.

## 5. Reference: what comes back

### The reply (`Message`)

One `Message` comes back from every `messages.create` call. The fields my loop reads:

| field | what it is | where my code uses it |
|---|---|---|
| `content` | a **list** of blocks, in the order the model produced them | `for block in response.content`; appended to `messages` |
| `stop_reason` | why the model stopped (below) | the `if / elif` chain in `run_agent` |
| `usage` | token counts for this one reply (below) | printed in Layer 1 Step 1; Layer 5 tracing will use it |
| `model` | the model that answered (echoes the provider's ID) | not used |
| `id`, `type`, `role` | the reply's id, always `"message"`, always `"assistant"` | not used |

The other fields (`stop_details`, `stop_sequence`, `container`, `diagnostics`) are optional and don't
come up for us yet; the appendix lists them.

### The blocks in `content`

A reply is not a string. It is a list of **blocks**, and each block has a `type` that says which fields
it has:

| block | `type` | its fields | what it is |
|---|---|---|---|
| `TextBlock` | `"text"` | `text` | words for the user |
| `ThinkingBlock` | `"thinking"` | `thinking`, `signature` | the model's reasoning (the text is usually empty to me; the tokens are still used) |
| `ToolUseBlock` | `"tool_use"` | `id`, `name`, `input` | a request to run one of my tools; `input` is a dict |

One reply can hold several blocks: `['thinking', 'tool_use', 'tool_use']` is two tool requests plus the
thinking before them. That is why the loop checks `block.type` on every block instead of assuming a
position, and why a one-block reply is still a list of one. Other kinds of block exist (server tools,
redacted thinking, and so on; the appendix lists them all) but need features I'm not using.

### `usage`: how it connects to the blocks

This is the connection that's easy to get wrong.

- **There is one `Usage` per `Message`. Blocks have no usage of their own.** None of the block
  classes has a usage field (the check script asserts this). So the token counts describe the reply
  as a whole, and I can't read "how many tokens was this text block" off the object.
- **`input_tokens`** counts everything I sent in that request: the hidden tool-use prompt, my tool
  definitions, any system prompt, and every message so far. It grows turn by turn because the whole
  history is re-sent (Layer 1 Step 1).
- **`output_tokens`** counts everything the model generated in that reply, **all blocks together**:
  thinking, text and tool requests. This is the number that `max_tokens` limits. That's why a reply
  made only of thinking can use the whole budget and leave no text (seen in Layer 2 Step 1d).
- **`output_tokens_details.thinking_tokens`** is an optional breakdown: how many of the output
  tokens were thinking. It exists in the SDK's type, but I haven't yet seen it filled in through the
  gateway, so don't assume it will be.
- **The cache fields** (`cache_creation_input_tokens`, `cache_read_input_tokens`, `cache_creation`)
  matter only with prompt caching (Layer 5). `service_tier`, `inference_geo` and `server_tool_use`
  can be ignored for now.
- **A run's total is a sum.** Each model call has its own `usage`. A run with three passes has three
  of them, and its cost is the sum. Because each pass re-sends the history, the input side of that
  sum grows faster than the conversation does.

### `stop_reason`

| value | meaning | what my loop does |
|---|---|---|
| `end_turn` | the model finished | return its text |
| `tool_use` | it wants tools run and is waiting for results | run them, send `tool_result`s, go round again |
| `max_tokens` | cut off by the length limit (thinking counts) | return what text there is, plus a note |
| `stop_sequence` | hit a stop string I supplied (I don't use any) | falls into the final `else` |
| `pause_turn`, `refusal`, `model_context_window_exceeded` | see the appendix | the final `else`: report and stop |

It is `None` only while a reply is still streaming (Layer 5).

## 6. Where each piece appears in my code

| piece | file | what happens |
|---|---|---|
| `client.messages.create(...)` | `loop.py` (`run_agent`) | one call per pass |
| `response.stop_reason`, `response.content` | `loop.py` | branch, then loop over blocks |
| `block.type`, `block.text` | `loop.py` (`collect_text`) | gather the text |
| `block.name`, `block.input`, `block.id` | `loop.py` | find and run the tool, label the result |
| tool definitions (`ToolParam`) | `tools.py` (`CALCULATOR`, `READ_FILE`, `LOAD_SKILL`) | passed as `tools=[...]` |
| `response.usage` | not read in the loop yet | Layer 5 tracing; printed in `layer1/` and `layer2/` scripts |
| a fake `Message` | `tests/fake_client.py` (`text_reply`, `tool_reply`) | `SimpleNamespace` with `stop_reason` and `content` |

A fake reply keeps only the attributes the loop reads (Layer 2 Step 2). The same shape, trimmed:

```
SimpleNamespace  (the fake Message)
|- stop_reason  "tool_use"
\- content  [ SimpleNamespace  (a fake ToolUseBlock) ]
                 |- type "tool_use"
                 |- id
                 |- name
                 \- input
```

## 7. Ways to explore this yourself

```python
type(response)                         # <class 'anthropic.types.message.Message'>
type(response.content[0])              # TextBlock, ThinkingBlock, or ToolUseBlock
type(response).model_fields.keys()     # every field the SDK defines for a reply
response.usage                         # the token counts for that reply
```

To refresh the appendix after upgrading the SDK, or to re-verify the claims in this text:

```
.venv/bin/python scripts/gen_sdk_reference.py          # rewrite the appendix (also runs the check)
.venv/bin/python scripts/gen_sdk_reference.py --check  # only verify the claims
```

## Appendix: field tables (generated from the SDK)

<!-- BEGIN GENERATED -->
SDK version: `anthropic` 1.11.0. Generated by `scripts/gen_sdk_reference.py`; do not edit by hand.

### Request side (plain dicts)

#### `MessageParam`

| key | required? | type |
|---|---|---|
| `content` | yes | `Required[Union[str, Iterable[Union[TextBlockParam, ImageBlockParam, DocumentBl...` |
| `role` | yes | `Required[Literal['user', 'assistant', 'system']]` |

#### `ToolParam`

| key | required? | type |
|---|---|---|
| `input_schema` | yes | `Required[Union[InputSchemaTyped, Dict[str, object]]]` |
| `name` | yes | `Required[str]` |
| `allowed_callers` | no | `List[Literal['direct', 'code_execution_20250825', 'code_execution_20260120', '...` |
| `cache_control` | no | `Optional[CacheControlEphemeralParam]` |
| `defer_loading` | no | `bool` |
| `description` | no | `str` |
| `eager_input_streaming` | no | `Optional[bool]` |
| `input_examples` | no | `Iterable[Dict[str, object]]` |
| `strict` | no | `bool` |
| `type` | no | `Optional[Literal['custom']]` |

#### `ToolResultBlockParam`

| key | required? | type |
|---|---|---|
| `tool_use_id` | yes | `Required[str]` |
| `type` | yes | `Required[Literal['tool_result']]` |
| `cache_control` | no | `Optional[CacheControlEphemeralParam]` |
| `content` | no | `Union[str, Iterable[Union[TextBlockParam, ImageBlockParam, SearchResultBlockPa...` |
| `is_error` | no | `bool` |
| `toolset_name` | no | `Optional[str]` |

#### `TextBlockParam`

| key | required? | type |
|---|---|---|
| `text` | yes | `Required[str]` |
| `type` | yes | `Required[Literal['text']]` |
| `cache_control` | no | `Optional[CacheControlEphemeralParam]` |
| `citations` | no | `Optional[Iterable[Union[CitationCharLocationParam, CitationPageLocationParam, ...` |

#### `ToolUseBlockParam`

| key | required? | type |
|---|---|---|
| `id` | yes | `Required[str]` |
| `input` | yes | `Required[Dict[str, object]]` |
| `name` | yes | `Required[str]` |
| `type` | yes | `Required[Literal['tool_use']]` |
| `cache_control` | no | `Optional[CacheControlEphemeralParam]` |
| `caller` | no | `Union[DirectCallerParam, ServerToolCallerParam, ServerToolCaller20260120Param]` |
| `toolset_name` | no | `Optional[str]` |

#### `ThinkingBlockParam`

| key | required? | type |
|---|---|---|
| `signature` | yes | `Required[str]` |
| `thinking` | yes | `Required[str]` |
| `type` | yes | `Required[Literal['thinking']]` |

#### `client.messages.create(...)` parameters

| parameter | required? |
|---|---|
| `max_tokens` | yes |
| `messages` | yes |
| `model` | yes |
| `cache_control` | no |
| `container` | no |
| `diagnostics` | no |
| `inference_geo` | no |
| `metadata` | no |
| `output_config` | no |
| `service_tier` | no |
| `stop_sequences` | no |
| `stream` | no |
| `system` | no |
| `thinking` | no |
| `tool_choice` | no |
| `tools` | no |
| `user_profile_id` | no |
| `workspace_id` | no |
| `extra_headers` | no |
| `extra_query` | no |
| `extra_body` | no |
| `timeout` | no |

### Response side (objects; read with a dot)

#### `Message`

| field | required? | type |
|---|---|---|
| `id` | yes | `str` |
| `container` | no | `Optional[Container]` |
| `content` | yes | `List[Annotated[Union[TextBlock, ThinkingBlock, RedactedThinkingBlock, ToolUseB...` |
| `diagnostics` | no | `Optional[Diagnostics]` |
| `model` | yes | `Union[Literal['claude-sonnet-5-5', 'claude-fable-5-1', 'claude-opus-5-5', 'cla...` |
| `role` | yes | `Literal['assistant']` |
| `stop_details` | no | `Optional[RefusalStopDetails]` |
| `stop_reason` | no | `Optional[Literal['end_turn', 'max_tokens', 'stop_sequence', 'tool_use', 'pause...` |
| `stop_sequence` | no | `Optional[str]` |
| `type` | yes | `Literal['message']` |
| `usage` | yes | `Usage` |

#### `Usage`

| field | required? | type |
|---|---|---|
| `cache_creation` | no | `Optional[CacheCreation]` |
| `cache_creation_input_tokens` | no | `Optional[int]` |
| `cache_read_input_tokens` | no | `Optional[int]` |
| `inference_geo` | no | `Optional[str]` |
| `input_tokens` | yes | `int` |
| `output_tokens` | yes | `int` |
| `output_tokens_details` | no | `Optional[OutputTokensDetails]` |
| `server_tool_use` | no | `Optional[ServerToolUsage]` |
| `service_tier` | no | `Optional[Literal['standard', 'priority', 'batch']]` |

#### `OutputTokensDetails`

| field | required? | type |
|---|---|---|
| `thinking_tokens` | yes | `int` |

#### `CacheCreation`

| field | required? | type |
|---|---|---|
| `ephemeral_1h_input_tokens` | yes | `int` |
| `ephemeral_5m_input_tokens` | yes | `int` |

#### `TextBlock`

| field | required? | type |
|---|---|---|
| `citations` | no | `Optional[List[Annotated[Union[CitationCharLocation, CitationPageLocation, Cita...` |
| `text` | yes | `str` |
| `type` | yes | `Literal['text']` |

#### `ThinkingBlock`

| field | required? | type |
|---|---|---|
| `signature` | yes | `str` |
| `thinking` | yes | `str` |
| `type` | yes | `Literal['thinking']` |

#### `ToolUseBlock`

| field | required? | type |
|---|---|---|
| `id` | yes | `str` |
| `caller` | no | `Optional[Annotated[Union[DirectCaller, ServerToolCaller, ServerToolCaller20260...` |
| `input` | yes | `Dict[str, object]` |
| `name` | yes | `str` |
| `type` | yes | `Literal['tool_use']` |
| `toolset_name` | no | `Optional[str]` |

#### Every kind of block that can appear in `Message.content`

`TextBlock`, `ThinkingBlock`, `RedactedThinkingBlock`, `ToolUseBlock`, `ServerToolUseBlock`, `WebSearchToolResultBlock`, `WebFetchToolResultBlock`, `CodeExecutionToolResultBlock`, `BashCodeExecutionToolResultBlock`, `TextEditorCodeExecutionToolResultBlock`, `ToolSearchToolResultBlock`, `ContainerUploadBlock`

#### `stop_reason` values

`end_turn`, `max_tokens`, `stop_sequence`, `tool_use`, `pause_turn`, `refusal`, `model_context_window_exceeded`

<!-- END GENERATED -->
