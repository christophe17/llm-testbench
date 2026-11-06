# Prompts and structured output

Prompts live in versioned files and travel with a fingerprint; a structured answer is a
schema the model must honour, with a bounded repair loop when it does not.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2f8", "primaryTextColor": "#1b1f24", "primaryBorderColor": "#5b6b82", "lineColor": "#7d8590", "textColor": "#1b1f24", "edgeLabelBackground": "#eef2f8", "noteBkgColor": "#fff4ce", "noteTextColor": "#1b1f24", "noteBorderColor": "#c9a227", "classText": "#1b1f24", "clusterBkg": "#f6f8fa", "clusterBorder": "#8b949e", "fontSize": "14px"}}}%%
classDiagram
  direction LR
  class PromptRegistry {
    +root : Path
    +from_settings(settings) PromptRegistry$
    +names() list~str~
    +get(name) PromptTemplate
    +render(prompt, variables) RenderedPrompt
  }
  class PromptTemplate {
    +name : str
    +version : int
    +description : str
    +body : str
    +path : Path
    +source_sha256 : str
  }
  class RenderedPrompt {
    +name : str
    +version : int
    +text : str
    +template_sha256 : str
    +sha256 : str
    +trace_metadata() dict~str, str~
  }
  class CompletionRequest {
    +json_schema : dict | None
    +metadata : dict~str, str~
  }
  class StructuredOutputs {
    +max_repairs : int
    +prepare(request, schema) CompletionRequest
    +complete(request, schema) StructuredResult~T~
  }
  class StructuredResult~T~ {
    +value : T
    +completion : Completion
    +attempts : int
    +repairs : tuple~str~
  }
  class LLMClient {
    +complete(request) Completion
    +native_json_schema(model) bool
  }
  class BackendConfig {
    +structured_output : StructuredOutputMode
  }
  class StructuredOutputMode {
    <<enumeration>>
    NATIVE
    PROMPT
  }
  PromptRegistry ..> PromptTemplate : get() parses prompts/name.md, frontmatter and body
  PromptRegistry ..> RenderedPrompt : render() with strict Jinja2, unknown variable fails
  RenderedPrompt ..> CompletionRequest : trace_metadata() goes into metadata
  StructuredOutputs --> LLMClient : complete(), then up to max_repairs more
  StructuredOutputs --> PromptRegistry : the repair prompt
  StructuredOutputs ..> CompletionRequest : prepare() sets json_schema or instructions
  StructuredOutputs ..> StructuredResult : complete() returns value plus history
  BackendConfig --> StructuredOutputMode : structured_output, per backend
  LLMClient ..> BackendConfig : native_json_schema(model) reads it
```

## How to read it

- A prompt is a Markdown file with a frontmatter (name, version, description). Two
  fingerprints follow it: the template's, and the rendered text's. Both land in the trace, so
  a regression in Langfuse can be matched to a prompt change.
- Rendering is strict: a variable the template needs and the caller forgot raises
  `PromptError` instead of producing an empty slot.
- Two ways to get JSON. `NATIVE`: the provider enforces the schema itself. `PROMPT`: the
  schema goes into the instructions and the answer is validated here. `prepare` picks one
  from the backend's `structured_output` mode.
- The repair loop is bounded. Each failed validation appends the error as a new turn and
  retries, at most `max_repairs` times; then `StructuredOutputError` carries the raw text and
  the last error. `StructuredResult.repairs` keeps the history for the numbers.

## In the code

[llm/prompts.py](../../src/llm_testbench/llm/prompts.py),
[llm/structured.py](../../src/llm_testbench/llm/structured.py), the prompts in
[prompts/](../../prompts/).

## In the notebooks

Notebook 01, part 4.7; notebook 02, part 4.2 for the `chat_answer` prompt.
