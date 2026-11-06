# The layers

Which subpackage depends on which, and where the outside world comes in. Every other diagram
of this folder zooms into one box of this one.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2f8", "primaryTextColor": "#1b1f24", "primaryBorderColor": "#5b6b82", "lineColor": "#7d8590", "textColor": "#1b1f24", "edgeLabelBackground": "#eef2f8", "noteBkgColor": "#fff4ce", "noteTextColor": "#1b1f24", "noteBorderColor": "#c9a227", "classText": "#1b1f24", "clusterBkg": "#f6f8fa", "clusterBorder": "#8b949e", "fontSize": "14px"}}}%%
flowchart TB
  subgraph pkg["src/llm_testbench"]
    direction TB
    app["app, the API<br/>app/main.py · app/chat.py · app/schemas.py · app/sse.py"]
    generation["generation, the cited answer<br/>generation/answer.py"]
    sources["sources, what can be searched<br/>sources/types.py · sources/documents.py"]
    ingest["ingest, from document to vector<br/>ingest/parsing.py · ingest/chunking.py · ingest/pipeline.py · ingest/store.py"]
    llm["llm, every model call<br/>llm/client.py · llm/registry.py · llm/governance.py · llm/resilience.py<br/>llm/providers/anthropic.py · llm/providers/openai_compatible.py"]
    eval["eval, datasets with ground truth<br/>eval/types.py · eval/loaders/beir.py · eval/loaders/qasper.py · eval/embeddings_bench.py"]
    obs["obs, trace attributes<br/>obs/tracing.py"]
    config["config.py, settings read by llm, eval and app"]
  end
  app --> generation
  app --> sources
  app --> llm
  generation --> llm
  generation --> sources
  sources --> ingest
  sources --> llm
  ingest --> llm
  eval --> ingest
  eval --> llm
  llm --> obs
  app --> obs
  llm --> anthropic[("Anthropic API, also through Bedrock")]
  llm --> openai[("OpenAI-compatible APIs")]
  ingest --> pg[("Postgres + pgvector")]
  obs --> otel[("OTel collector, Langfuse")]
  eval --> hf[("Hugging Face datasets")]
```

## How to read it

- An arrow `A --> B` means "A imports B". The direction never reverses: `llm` knows nothing
  about documents or the API, `ingest` and `sources` know nothing about HTTP.
- `llm` is the only box that talks to a model provider. Embeddings for the index
  (`ingest`), for the question (`sources`) and for the benchmark (`eval`) all go through its
  `LLMClient`, so governance, retries, cost and traces apply to every call the same way.
- `sources` depends on `ingest` for one thing: the `PgVectorStore` it searches. The API
  never sees the store, only a `Source`.
- `eval` depends on `ingest` only to turn a QASPER paper into a `ParsedDocument`.
- `obs` holds the attribute names of the traces, nothing else: the spans are opened by
  `llm` and `app`.

## Next

[01 anatomy of a call](01-call-anatomy.md) opens the `llm` box.
