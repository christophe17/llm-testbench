# ADR 006 — LLM layer: two-implementation abstraction, data governance by construction

- **Date**: 2026-09-03
- **Status**: accepted

## Context

The brief freezes a multi-provider abstraction from the first call (OpenAI ↔ Anthropic ↔
Mistral ↔ local model), Bedrock as one provider among others in the cloud, and prompts in
versioned files. At the start of phase 1, two new elements: the request to
go through OpenRouter for the whole roadmap ("switch LLMs easily"), and the announcement
of an upcoming **data governance** constraint, its nature still unknown, to be
taken into account as early as possible (clients in view, Swiss target: banking, pharma,
insurance, data residency and on-premise).

## Options considered

**For the abstraction.**

1. **OpenRouter as the single path.** A single OpenAI-compatible client, a catalog of
   models without a dedicated key. Rejected as the single path: an additional American
   intermediary that routes each model to a third-party host with no control over the
   inference region (incompatible with the announced constraint); lowest common
   denominator (no batch API, structured outputs and prompt cache partially exposed);
   normalized token counting and a commission on credits that blur the per-request
   cost of phase 5.
2. **LiteLLM** (or equivalent) as the abstraction. Covers a hundred providers, but hides
   precisely the mechanics the project wants to expose (retries, breaker, budget, cache),
   and adds a heavy dependency. Compared in notebook 1, not stacked.
3. **In-house abstraction with two implementations** on the official SDKs: `anthropic`
   (which also serves Bedrock via its Bedrock client, same Messages API) and `openai` with a
   base URL (OpenAI, OpenRouter, Mistral, then vLLM/Ollama in phase 6). **Selected.** Two
   implementations cover six backends; the model is a `backend/model` string in
   configuration; OpenRouter remains a **breadth backend** for comparisons.

**For governance.**

1. **A document** listing the authorized providers. Rejected: not verifiable, forgotten at
   the first refactor, invisible in the traces.
2. **A property of the LLM layer**, checked on every call and traced. **Selected.**

## Decision

### Structure

Module `src/llm_testbench/llm/`:

| File | Role |
|---|---|
| `types.py` | `Message`, `CompletionRequest`, `Completion`, `Usage`, `StreamChunk`, `ModelRef` |
| `errors.py` | typed error hierarchy, with a `retryable` flag |
| `provider.py` | `LLMProvider` protocol: `complete()`, `stream()`, declared capabilities |
| `providers/anthropic.py`, `providers/openai_compatible.py` | the two implementations |
| `registry.py` | backends and models from `config/llm_backends.toml`, `backend/model` resolution |
| `governance.py` | data classes, governance metadata, policy, decision |
| `resilience.py` | retry with exponential backoff and jitter, three-state circuit breaker, timeouts |
| `budget.py` | token budget per request and per sliding window |
| `cache.py` | exact cache (canonical hash of the request) and semantic cache (pgvector) |
| `structured.py` | structured output: native schema when the backend supports it, Pydantic validation, bounded repair loop |
| `prompts.py` | versioned prompt registry (`prompts/*.md`, header + strict Jinja2 body), SHA-256 hash |
| `cost.py` | dated price table `config/llm_pricing.toml`, cost per call, `None` if unknown |
| `client.py` | `LLMClient` facade: governance → cache → breaker → retry → provider → budget → cost → trace |

### Non-obvious choices

- **The SDKs do not retry** (`max_retries=0`): a single retry policy, ours,
  observable per attempt, aware of the budget and the breaker. Two stacked retry
  layers multiply the attempts without anyone seeing it.
- **Structured output**: native JSON schema (`output_config.format` at Anthropic,
  `response_format` json_schema at OpenAI and the compatibles that support it), otherwise an
  instruction in the prompt and extraction. In every case Pydantic validation, then at most
  N repair attempts where the validation error is sent back to the model. Each
  attempt is traced: the repair rate is a metric, not a secret.
- **Exact cache** on the canonical hash of the entire request (backend, model,
  messages, parameters, prompt version). **Semantic cache** on the embedding of the last
  user message, configurable similarity threshold, reserved for requests without history.
  Both in Postgres; an in-memory backend for tests. A cache hit is traced
  as such, with zero cost.
- **Streaming**: async generator of `StreamChunk`; closing the generator
  (SSE client disconnect) closes the provider stream. No hidden accumulation.
- **Prompts**: `prompts/<name>.md` files, header (name, version, description, recommended
  backends) and Jinja2 body with strict variables (a missing variable is an error,
  not an empty string). The render carries its SHA-256 hash, written into the trace: we
  will always know which exact text produced which number. The phase 5 registry
  (hot rollback) will build on it.
- **Cost**: versioned price table with verification date and source. A model with no
  known price yields a `None` cost and a trace attribute `cost.unknown=true`: a missing
  number is better than an invented one.
- **Configuration in TOML** (`tomllib`, standard library): readable, typed, no
  dependency.

### Data governance

- Each request carries a **data class**: `public`, `internal`, `confidential`,
  `personal`, `regulated`. Without an explicit class, a request is refused: the implicit
  default is the first loophole.
- Each backend declares, in `config/llm_backends.toml`, its **governance
  metadata**: legal entity and country, inference region (`eu`, `us`, `self`,
  `variable`), default retention and availability of zero retention, use of
  inputs for training, subprocessors (OpenRouter: variable hosts),
  certifications. These metadata are claims to be verified contractually, not
  guarantees: their verification date is recorded.
- A **policy** maps each class to requirements and decides, **denying by
  default**, before any network call. Initial policy, **provisional** as long as the
  real constraints are not known: `public` with no requirement; `internal` requires
  no training on inputs; `confidential`, `personal`, `regulated`
  require region `eu` or `self`, zero retention and no training. It lives in
  a configuration file, not in the code.
- The **decision** (class, backend, outcome, rule) is an attribute of the trace of each
  call, alongside the exact model identifier and the region. A refusal is a typed
  exception, never a silent fallback to another backend: the fallback is a
  decision of the caller, traced as well.
- The same policy applies to **embeddings** (the text leaves in the same way) and,
  in phase 2, to the **judge**.
- On the testbench, all data is public: the mechanism is exercised by the tests
  and demonstrated in the notebook (a request labeled `regulated` refuses OpenRouter). From
  phase 6 on, the master table gains a "cost of governance" row:
  latency, price and quality of the compliant path against the unrestricted path.

## Consequences

Default generator for phase 1: `anthropic/claude-sonnet-5`; second provider OpenAI,
which will serve as judge in phase 2 (judge ≠ generator). OpenRouter and Bedrock are backends
declared from phase 1, Bedrock enabled with the cloud infra. The governance policy will be
hardened as the constraints become clearer, without touching the code. Cost: two SDKs to follow
instead of one, and a price table to maintain by hand — that is the price of a cost
figure one can believe. Phase 7 (PII, AI Act) and phase 4.7 (permissions) plug
into the same trace attributes.
