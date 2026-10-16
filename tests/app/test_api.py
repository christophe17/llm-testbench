"""L'API sur un client LLM à provider simulé et une source en mémoire : aucun réseau,
aucune base. On teste le transport (JSON, SSE, codes d'erreur), pas le retrieval."""

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from llm_testbench.app.main import create_app
from llm_testbench.config import Settings
from llm_testbench.generation.answer import REFUSAL_SENTINEL
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.errors import ProviderUnavailableError
from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.resilience import RetryPolicy
from llm_testbench.sources.types import (
    Capability,
    Evidence,
    Provenance,
    SearchQuery,
    SourceInfo,
    SourceKind,
)
from tests.llm.fakes import FakeProvider, make_completion


class MemorySource:
    key = "docs:memory"
    kind = SourceKind.DOCUMENTS
    capabilities = frozenset({Capability.SEARCH})

    def __init__(self) -> None:
        self.queries: list[SearchQuery] = []

    async def search(self, query: SearchQuery) -> list[Evidence]:
        self.queries.append(query)
        return [
            Evidence(
                text=f"Extrait {i} sur {query.text}",
                score=1.0 - i / 10,
                rank=i,
                provenance=Provenance(
                    source_key=self.key, document_id=f"doc{i}", locator=f"partie {i}", title=f"D{i}"
                ),
            )
            for i in range(1, min(query.k, 3) + 1)
        ]

    async def fetch(self, document_id: str) -> Evidence | None:
        return None

    async def describe(self) -> SourceInfo:
        return SourceInfo(
            key=self.key, kind=self.kind, capabilities=self.capabilities, document_count=3
        )


async def _fake_sleep(_: float) -> None:
    return None


def build_client(provider: FakeProvider) -> LLMClient:
    client = LLMClient.from_settings(
        retry_policy=RetryPolicy(max_attempts=2, base_delay_s=0.0, jitter=0.0), sleep=_fake_sleep
    )
    client.register_provider("anthropic", provider)
    return client


@pytest.fixture
def source() -> MemorySource:
    return MemorySource()


def make_app(provider: FakeProvider, source: MemorySource) -> Iterator[TestClient]:
    app = create_app(Settings(), llm_client=build_client(provider), source=source)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def api(source: MemorySource) -> Iterator[TestClient]:
    yield from make_app(FakeProvider(script=[make_completion("Paris [2], sûrement [1].")]), source)


def test_health_and_readiness(api: TestClient) -> None:
    assert api.get("/healthz").json() == {"status": "ok"}
    assert api.get("/readyz").json() == {"status": "ready"}


def test_not_ready_without_database() -> None:
    app = create_app(Settings(database_url=None), llm_client=build_client(FakeProvider()))
    with TestClient(app) as client:
        ready = client.get("/readyz")
        assert ready.status_code == 503
        assert "DATABASE_URL" in ready.json()["detail"]
        assert client.post("/chat", json={"question": "x"}).status_code == 503


def test_chat_returns_answer_citations_and_evidence(api: TestClient, source: MemorySource) -> None:
    response = api.post("/chat", json={"question": "Capitale ?", "k": 2})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"] == "Paris [2], sûrement [1]."
    assert body["refused"] is False
    assert [c["index"] for c in body["citations"]] == [2, 1]
    assert body["citations"][0]["label"] == "docs:memory › D2 › partie 2"
    assert body["unknown_citations"] == []
    assert [e["rank"] for e in body["evidence"]] == [1, 2]
    assert body["backend"] == "anthropic"
    assert body["cost_usd"] == pytest.approx(0.007)
    assert body["attempts"] == 1
    assert source.queries[0].k == 2
    assert source.queries[0].data_class is DataClass.PUBLIC


def test_chat_reports_refusal_and_unknown_citations(source: MemorySource) -> None:
    provider = FakeProvider(script=[make_completion(REFUSAL_SENTINEL), make_completion("Oui [9].")])
    for api in make_app(provider, source):
        refused = api.post("/chat", json={"question": "Et la lune ?"}).json()
        assert refused["refused"] is True
        assert refused["citations"] == []
        suspicious = api.post("/chat", json={"question": "Encore ?"}).json()
        assert suspicious["unknown_citations"] == [9]


def test_validation_errors_are_422(api: TestClient) -> None:
    assert api.post("/chat", json={"question": ""}).status_code == 422
    assert api.post("/chat", json={"question": "x", "k": 99}).status_code == 422
    assert api.post("/chat", json={"question": "x", "extra": 1}).status_code == 422


def test_governance_violation_is_403_with_reasons(api: TestClient) -> None:
    response = api.post("/chat", json={"question": "secret", "data_class": "regulated"})
    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "governance"
    assert any("région" in r for r in body["reasons"])


def test_upstream_outage_is_503(source: MemorySource) -> None:
    down = ProviderUnavailableError("503", backend="anthropic", status_code=503)
    for api in make_app(FakeProvider(script=[down, down]), source):
        response = api.post("/chat", json={"question": "x"})
        assert response.status_code == 503
        assert response.json()["error"] == "upstream_unavailable"


def test_unknown_backend_is_400(api: TestClient) -> None:
    response = api.post("/chat", json={"question": "x", "model": "ghost/model"})
    assert response.status_code == 400
    assert response.json()["error"] == "unknown_backend"


def test_sources_endpoint(api: TestClient) -> None:
    body = api.get("/sources").json()
    assert body == [
        {
            "key": "docs:memory",
            "kind": "documents",
            "capabilities": ["search"],
            "description": "",
            "document_count": 3,
        }
    ]


def test_stream_sends_evidence_then_tokens_then_done(api: TestClient) -> None:
    with api.stream("POST", "/chat/stream", json={"question": "Capitale ?", "k": 1}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        raw = b"".join(response.iter_bytes()).decode()
    blocks = [b for b in raw.split("\n\n") if b.strip()]
    kinds = [b.splitlines()[0].removeprefix("event: ") for b in blocks]
    assert kinds[0] == "retrieval"
    assert kinds[-1] == "done"
    assert kinds[1:-1] == ["token", "token"]
    done = json.loads(blocks[-1].splitlines()[1].removeprefix("data: "))
    assert done["answer"]["answer"] == "Bonjour"
    assert done["answer"]["usage"]["output_tokens"] == 5
    assert done["answer"]["cost_usd"] == pytest.approx(10 * 2e-6 + 5 * 10e-6)
