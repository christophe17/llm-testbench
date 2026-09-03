"""Le service de chat : retrieval → requête citée → génération → parsing des citations.

Indépendant du transport : la route JSON et la route SSE appellent le même service, et
le même parseur de réponse (ADR 007). Le flux renvoie les preuves **avant** le premier
token, pour que le client puisse afficher les sources pendant que la réponse s'écrit.
"""

from collections.abc import AsyncIterator

from opentelemetry import trace

from llm_testbench.app.schemas import (
    ChatEvent,
    ChatRequest,
    ChatResponse,
    CitationOut,
    EvidenceOut,
)
from llm_testbench.generation.answer import AnswerBuilder, ParsedAnswer, parse_answer
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.types import Completion, ModelRef, Usage
from llm_testbench.sources.types import Evidence, SearchQuery, Source


def _current_trace_id() -> str | None:
    context = trace.get_current_span().get_span_context()
    return f"{context.trace_id:032x}" if context.is_valid else None


class ChatService:
    def __init__(
        self,
        *,
        client: LLMClient,
        source: Source,
        builder: AnswerBuilder,
        default_model: ModelRef,
        max_output_tokens: int = 1024,
    ) -> None:
        self._client = client
        self._source = source
        self._builder = builder
        self.default_model = default_model
        self.max_output_tokens = max_output_tokens

    def _model(self, request: ChatRequest) -> ModelRef:
        return ModelRef.parse(request.model) if request.model else self.default_model

    async def _retrieve(self, request: ChatRequest) -> list[Evidence]:
        return await self._source.search(
            SearchQuery(text=request.question, k=request.k, data_class=request.data_class)
        )

    @staticmethod
    def _response(
        parsed: ParsedAnswer, evidence: list[Evidence], completion: Completion
    ) -> ChatResponse:
        return ChatResponse(
            answer=parsed.text,
            refused=parsed.refused,
            citations=[CitationOut.from_citation(c) for c in parsed.citations],
            unknown_citations=list(parsed.unknown_indexes),
            evidence=[EvidenceOut.from_evidence(e) for e in evidence],
            model=completion.model,
            backend=completion.backend,
            usage=completion.usage,
            cost_usd=completion.cost_usd,
            latency_ms=completion.latency_ms,
            cached=completion.cached,
            attempts=completion.attempts,
            trace_id=_current_trace_id(),
        )

    async def answer(self, request: ChatRequest) -> ChatResponse:
        model = self._model(request)
        evidence = await self._retrieve(request)
        completion_request = self._builder.build_request(
            request.question,
            evidence,
            model=model,
            data_class=request.data_class,
            max_output_tokens=self.max_output_tokens,
        )
        completion = await self._client.complete(completion_request)
        parsed = parse_answer(completion.text, evidence)
        return self._response(parsed, evidence, completion)

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        model = self._model(request)
        evidence = await self._retrieve(request)
        yield ChatEvent(kind="retrieval", evidence=[EvidenceOut.from_evidence(e) for e in evidence])
        completion_request = self._builder.build_request(
            request.question,
            evidence,
            model=model,
            data_class=request.data_class,
            max_output_tokens=self.max_output_tokens,
        )
        parts: list[str] = []
        usage = Usage()
        cost: float | None = None
        served_model = model.model
        async for chunk in self._client.stream(completion_request):
            if chunk.kind == "text":
                parts.append(chunk.text)
                yield ChatEvent(kind="token", text=chunk.text)
            elif chunk.kind == "usage" and chunk.usage is not None:
                usage, cost = chunk.usage, chunk.cost_usd
                served_model = chunk.model or served_model
            elif chunk.kind == "end":
                served_model = chunk.model or served_model
        text = "".join(parts)
        completion = Completion(
            text=text,
            model=served_model,
            backend=model.backend,
            usage=usage,
            finish_reason="stop",  # type: ignore[arg-type]
            cost_usd=cost,
        )
        parsed = parse_answer(text, evidence)
        yield ChatEvent(kind="done", answer=self._response(parsed, evidence, completion))
