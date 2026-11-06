# Anatomy of a call

The data types only: what goes into a model call and what comes back. No behaviour here,
the mechanism is in [02 the client and its providers](02-client-and-providers.md).

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2f8", "primaryTextColor": "#1b1f24", "primaryBorderColor": "#5b6b82", "lineColor": "#7d8590", "textColor": "#1b1f24", "edgeLabelBackground": "#eef2f8", "noteBkgColor": "#fff4ce", "noteTextColor": "#1b1f24", "noteBorderColor": "#c9a227", "classText": "#1b1f24", "clusterBkg": "#f6f8fa", "clusterBorder": "#8b949e", "fontSize": "14px"}}}%%
classDiagram
  direction LR
  class CompletionRequest {
    +model : ModelRef
    +messages : tuple~Message~
    +data_class : DataClass
    +max_output_tokens : int
    +temperature : float | None
    +json_schema : dict | None
    +timeout_s : float | None
    +metadata : dict~str, str~
    +system : str | None
    +turns : tuple~Message~
    +with_messages(messages) CompletionRequest
  }
  class Message {
    +role : Role
    +content : str
  }
  class Role {
    <<enumeration>>
    SYSTEM
    USER
    ASSISTANT
  }
  class ModelRef {
    +backend : str
    +model : str
    +parse(ref) ModelRef$
  }
  class DataClass {
    <<enumeration>>
    PUBLIC
    INTERNAL
    CONFIDENTIAL
    PERSONAL
    REGULATED
  }
  class Completion {
    +text : str
    +model : str
    +backend : str
    +usage : Usage
    +finish_reason : FinishReason
    +latency_ms : float
    +cost_usd : float | None
    +cached : bool
    +attempts : int
    +usage_reported : bool
  }
  class Usage {
    +input_tokens : int
    +output_tokens : int
    +cache_read_tokens : int
    +cache_write_tokens : int
    +total_tokens : int
  }
  class FinishReason {
    <<enumeration>>
    STOP
    LENGTH
    CONTENT_FILTER
    REFUSAL
    TOOL_USE
    OTHER
  }
  class StreamChunk {
    +kind : text, usage or end
    +text : str
    +usage : Usage | None
    +cost_usd : float | None
    +finish_reason : FinishReason | None
  }
  CompletionRequest *-- Message : messages, system first
  Message --> Role : role
  CompletionRequest --> ModelRef : model, parsed from backend/model
  CompletionRequest --> DataClass : data_class, mandatory
  Completion --> Usage : usage
  Completion --> FinishReason : finish_reason
  StreamChunk --> Usage : usage, only on the usage chunk
  CompletionRequest ..> Completion : complete() returns
  CompletionRequest ..> StreamChunk : stream() yields
```

## How to read it

- Everything is a frozen Pydantic model or a string enum: a request is a value, never
  mutated. `with_messages` returns a new request, which is how the structured-output repair
  loop appends a turn.
- `data_class` has no default. The caller must say what kind of data leaves the building,
  and [03 governance](03-governance.md) decides whether the backend may receive it.
- `ModelRef` is the string `backend/model` split in two. The backend half is a key of the
  registry, the model half is whatever the provider understands.
- `Completion.usage_reported` is false when the provider gave no token counts; the cost is
  then unknown rather than zero. `cached` and `attempts` are filled by the client, not by the
  provider.
- A stream is a sequence of `StreamChunk`: many `text`, then one `usage`, then `end`. The
  client in [09 the chat path](09-chat-path.md) rebuilds a `Completion` from them.

## In the code

[llm/types.py](../../src/llm_testbench/llm/types.py), and `DataClass` in
[llm/governance.py](../../src/llm_testbench/llm/governance.py).

## In the notebooks

Notebook 01, part 3.1, reads these types before the first call.
