"""Common types of the LLM layer: request, response, usage, stream.

They are **SDK-independent**: this is the contract that the providers translate. Everything
is frozen (``frozen``): a request is not modified along the way, it is derived
(:meth:`CompletionRequest.with_messages`), which makes the cache and the trace reliable.
"""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from llm_testbench.llm.governance import DataClass


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Role
    content: str


class ModelRef(BaseModel):
    """``backend/model`` reference. The backend is an entry of the configuration; the
    model is free-form and may itself contain ``/`` (OpenRouter:
    ``openrouter/mistralai/mistral-large``)."""

    model_config = ConfigDict(frozen=True)

    backend: str
    model: str

    @classmethod
    def parse(cls, ref: str) -> "ModelRef":
        backend, sep, model = ref.partition("/")
        if not sep or not backend or not model:
            raise ValueError(f"model reference expected in the form backend/model, got {ref!r}")
        return cls(backend=backend, model=model)

    def __str__(self) -> str:
        return f"{self.backend}/{self.model}"


class CompletionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: ModelRef
    messages: tuple[Message, ...] = Field(min_length=1)
    data_class: DataClass
    """Required, with no default: the implicit default would be the first hole."""

    max_output_tokens: int = Field(default=1024, ge=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    """``None``: provider default. ``0`` does not guarantee determinism (phase 5B)."""

    stop: tuple[str, ...] = ()
    seed: int | None = None
    json_schema: dict[str, Any] | None = None
    """JSON schema expected as output. The provider enforces it natively if it can, otherwise
    the facade injects it into the prompt and validates afterwards (``structured.py``)."""

    reasoning_effort: Literal["low", "medium", "high"] | None = None
    """Reasoning effort, when the backend has this setting (``output_config.effort`` at
    Anthropic, ``reasoning_effort`` at OpenAI). ``None``: provider default."""

    timeout_s: float | None = Field(default=None, gt=0)
    metadata: dict[str, str] = Field(default_factory=dict)
    """Trace information (prompt name/version/fingerprint…). Not part of the cache key."""

    @field_validator("messages")
    @classmethod
    def _system_only_first(cls, messages: tuple[Message, ...]) -> tuple[Message, ...]:
        for index, message in enumerate(messages):
            if message.role is Role.SYSTEM and index != 0:
                raise ValueError("a system message is only allowed in first position")
        return messages

    @property
    def system(self) -> str | None:
        first = self.messages[0]
        return first.content if first.role is Role.SYSTEM else None

    @property
    def turns(self) -> tuple[Message, ...]:
        """The non-system messages, in order."""
        return tuple(m for m in self.messages if m.role is not Role.SYSTEM)

    def with_messages(self, messages: tuple[Message, ...]) -> "CompletionRequest":
        return self.model_copy(update={"messages": messages})


class Usage(BaseModel):
    """Tokens consumed, normalized across providers.

    ``input_tokens`` counts the input tokens **not served by the cache** (billed at full
    price). Anthropic reports them this way natively; OpenAI includes cached tokens in
    ``prompt_tokens``, and the provider does the subtraction. Without this normalization, the
    per-request cost of phase 5 would compare different things.
    """

    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)

    @property
    def total_input_tokens(self) -> int:
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.output_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
        )


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    """``max_output_tokens`` reached: the answer is truncated, not finished."""
    CONTENT_FILTER = "content_filter"
    REFUSAL = "refusal"
    TOOL_USE = "tool_use"
    OTHER = "other"


class Completion(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    model: str
    """Exact identifier returned by the provider — not the one requested. A provider may
    serve a different revision than the one we think (phase 5 runbook)."""
    backend: str
    usage: Usage
    finish_reason: FinishReason
    latency_ms: float = 0.0
    cost_usd: float | None = None
    """``None`` = unknown price, never 0 by default."""
    cached: bool = False
    attempts: int = 1
    provider_message_id: str | None = None
    usage_reported: bool = True
    """False if the provider returned no usage: the cost is then unknown, not zero."""


class StreamChunk(BaseModel):
    """Element of a stream: text, then usage, then the end (in this order)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["text", "usage", "end"]
    text: str = ""
    usage: Usage | None = None
    cost_usd: float | None = None
    finish_reason: FinishReason | None = None
    model: str | None = None
