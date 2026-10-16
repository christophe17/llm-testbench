from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from llm_testbench.obs.tracing import configure_tracing, get_tracer, langfuse_otlp_headers


def test_configure_tracing_with_an_exporter_exports_synchronously() -> None:
    exporter = InMemorySpanExporter()
    provider = configure_tracing(service_name="svc", exporter=exporter, set_global=False)
    with get_tracer(provider).start_as_current_span("work") as span:
        span.set_attribute("k", "v")
    (exported,) = exporter.get_finished_spans()
    assert exported.name == "work"
    assert dict(exported.attributes or {}) == {"k": "v"}
    assert exported.resource.attributes["service.name"] == "svc"


def test_langfuse_headers_are_basic_auth_of_public_and_secret_keys() -> None:
    assert langfuse_otlp_headers("pk", "sk") == {"Authorization": "Basic cGs6c2s="}
