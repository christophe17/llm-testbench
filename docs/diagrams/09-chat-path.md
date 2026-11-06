# The chat path

What happens between a question and a cited answer: retrieval, prompt, generation, parsing.
The JSON route and the SSE route call the same service.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2f8", "primaryTextColor": "#1b1f24", "primaryBorderColor": "#5b6b82", "lineColor": "#7d8590", "textColor": "#1b1f24", "edgeLabelBackground": "#eef2f8", "noteBkgColor": "#fff4ce", "noteTextColor": "#1b1f24", "noteBorderColor": "#c9a227", "classText": "#1b1f24", "clusterBkg": "#f6f8fa", "clusterBorder": "#8b949e", "fontSize": "14px"}}}%%
classDiagram
  direction LR
  class ChatService {
    +default_model : ModelRef
    +max_output_tokens : int
    +answer(request) ChatResponse
    +stream(request) AsyncIterator~ChatEvent~
  }
  class ChatRequest {
    +question : str
    +k : int
    +data_class : DataClass
    +model : str | None
  }
  class ChatResponse {
    +answer : str
    +refused : bool
    +citations : list~CitationOut~
    +unknown_citations : list~int~
    +evidence : list~EvidenceOut~
    +model : str
    +usage : Usage
    +cost_usd : float | None
    +latency_ms : float
    +cached : bool
    +attempts : int
    +trace_id : str | None
  }
  class ChatEvent {
    +kind : retrieval, token, done or error
    +evidence : list~EvidenceOut~ | None
    +text : str | None
    +answer : ChatResponse | None
    +message : str | None
  }
  class EvidenceOut {
    +rank : int
    +score : float
    +text : str
    +provenance : Provenance
    +from_evidence(evidence) EvidenceOut$
  }
  class CitationOut {
    +index : int
    +label : str
    +provenance : Provenance
    +from_citation(citation) CitationOut$
  }
  class Source {
    <<Protocol>>
    +search(query) list~Evidence~
  }
  class AnswerBuilder {
    +build_request(question, evidence, model, data_class, max_output_tokens) CompletionRequest
  }
  class PromptRegistry {
    +render(prompt, variables) RenderedPrompt
  }
  class LLMClient {
    +complete(request) Completion
    +stream(request) AsyncIterator~StreamChunk~
  }
  class ParsedAnswer {
    +text : str
    +refused : bool
    +citations : tuple~Citation~
    +unknown_indexes : tuple~int~
    +cited_indexes : tuple~int~
  }
  ChatService --> Source : 1. search(SearchQuery) gives ranked Evidence
  ChatService --> AnswerBuilder : 2. build_request(question, evidence)
  AnswerBuilder --> PromptRegistry : renders chat_answer with the numbered context
  ChatService --> LLMClient : 3. complete() or stream()
  ChatService ..> ParsedAnswer : 4. parse_answer(text, evidence), a module function
  ChatService ..> ChatRequest : answer() and stream() take
  ChatService ..> ChatResponse : answer() returns
  ChatService ..> ChatEvent : stream() yields retrieval, token..., done
  ChatEvent --> EvidenceOut : evidence, in the retrieval event, before any token
  ChatEvent --> ChatResponse : answer, in the done event
  ChatResponse *-- CitationOut : citations
  ChatResponse *-- EvidenceOut : evidence
```

## How to read it

- Four steps, always in this order. The service does not know whether it serves JSON or SSE;
  the routes in `app/main.py` only choose between `answer` and `stream`.
- The service depends on the `Source` protocol, not on `DocumentSource`. Phase 4 adds
  SQL and API sources behind the same arrow.
- Citations are numbers in the text, `[2]`, matched to the evidence by position. A number
  that matches nothing is kept in `unknown_citations`: a hallucinated citation is measured,
  not hidden.
- The refusal is an exact sentence, recognised up to case and accents, and it must be the
  whole answer. A sentence rather than a JSON field so that streaming still works.
- In the stream, the evidence event comes before the first token, so a client can show the
  sources while the answer is being written. The `done` event carries the same
  `ChatResponse` the JSON route would have returned, rebuilt from the chunks.
- `*Out` schemas are the API's own types, converted from the internal `Evidence` and
  `Citation`, so the wire format can change without touching the service.

## In the code

[app/chat.py](../../src/llm_testbench/app/chat.py),
[app/schemas.py](../../src/llm_testbench/app/schemas.py),
[app/main.py](../../src/llm_testbench/app/main.py),
[generation/answer.py](../../src/llm_testbench/generation/answer.py).

## In the notebooks

Notebook 02, parts 4.1 to 4.4.
