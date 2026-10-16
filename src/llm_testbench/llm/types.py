"""Types communs de la couche LLM : requête, réponse, usage, flux.

Ils sont **indépendants des SDK** : c'est le contrat que les providers traduisent. Tout
est figé (``frozen``) : une requête ne se modifie pas en route, elle se dérive
(:meth:`CompletionRequest.with_messages`), ce qui rend le cache et la trace fiables.
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
    """Référence ``backend/modèle``. Le backend est une entrée de la configuration ; le
    modèle est libre et peut lui-même contenir des ``/`` (OpenRouter :
    ``openrouter/mistralai/mistral-large``)."""

    model_config = ConfigDict(frozen=True)

    backend: str
    model: str

    @classmethod
    def parse(cls, ref: str) -> "ModelRef":
        backend, sep, model = ref.partition("/")
        if not sep or not backend or not model:
            raise ValueError(
                f"référence de modèle attendue sous la forme backend/modèle, reçu {ref!r}"
            )
        return cls(backend=backend, model=model)

    def __str__(self) -> str:
        return f"{self.backend}/{self.model}"


class CompletionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: ModelRef
    messages: tuple[Message, ...] = Field(min_length=1)
    data_class: DataClass
    """Obligatoire, sans défaut : le défaut implicite serait la première faille."""

    max_output_tokens: int = Field(default=1024, ge=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    """``None`` : défaut du provider. ``0`` ne garantit pas le déterminisme (phase 5B)."""

    stop: tuple[str, ...] = ()
    seed: int | None = None
    json_schema: dict[str, Any] | None = None
    """Schéma JSON attendu en sortie. Le provider l'impose nativement s'il sait, sinon la
    façade l'injecte dans le prompt et valide après coup (``structured.py``)."""

    reasoning_effort: Literal["low", "medium", "high"] | None = None
    """Effort de raisonnement, quand le backend a ce réglage (``output_config.effort`` chez
    Anthropic, ``reasoning_effort`` chez OpenAI). ``None`` : défaut du provider."""

    timeout_s: float | None = Field(default=None, gt=0)
    metadata: dict[str, str] = Field(default_factory=dict)
    """Informations de trace (nom/version/empreinte du prompt…). Hors clé de cache."""

    @field_validator("messages")
    @classmethod
    def _system_only_first(cls, messages: tuple[Message, ...]) -> tuple[Message, ...]:
        for index, message in enumerate(messages):
            if message.role is Role.SYSTEM and index != 0:
                raise ValueError("un message system n'est admis qu'en première position")
        return messages

    @property
    def system(self) -> str | None:
        first = self.messages[0]
        return first.content if first.role is Role.SYSTEM else None

    @property
    def turns(self) -> tuple[Message, ...]:
        """Les messages hors system, dans l'ordre."""
        return tuple(m for m in self.messages if m.role is not Role.SYSTEM)

    def with_messages(self, messages: tuple[Message, ...]) -> "CompletionRequest":
        return self.model_copy(update={"messages": messages})


class Usage(BaseModel):
    """Tokens consommés, normalisés entre providers.

    ``input_tokens`` compte les tokens d'entrée **non servis par le cache** (facturés plein
    tarif). Anthropic les rapporte ainsi nativement ; OpenAI inclut les tokens cachés dans
    ``prompt_tokens``, et le provider fait la soustraction. Sans cette normalisation, le
    coût par requête de la phase 5 comparerait des choses différentes.
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
    """``max_output_tokens`` atteint : la réponse est tronquée, pas terminée."""
    CONTENT_FILTER = "content_filter"
    REFUSAL = "refusal"
    TOOL_USE = "tool_use"
    OTHER = "other"


class Completion(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    model: str
    """Identifiant exact renvoyé par le provider — pas celui demandé. Un provider peut
    servir une autre révision que celle qu'on croit (runbook phase 5)."""
    backend: str
    usage: Usage
    finish_reason: FinishReason
    latency_ms: float = 0.0
    cost_usd: float | None = None
    """``None`` = prix inconnu, jamais 0 par défaut."""
    cached: bool = False
    attempts: int = 1
    provider_message_id: str | None = None
    usage_reported: bool = True
    """False si le provider n'a pas renvoyé d'usage : le coût est alors inconnu, pas nul."""


class StreamChunk(BaseModel):
    """Élément d'un flux : du texte, puis l'usage, puis la fin (dans cet ordre)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["text", "usage", "end"]
    text: str = ""
    usage: Usage | None = None
    cost_usd: float | None = None
    finish_reason: FinishReason | None = None
    model: str | None = None
