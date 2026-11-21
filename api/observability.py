"""OpenTelemetry spans exported to Langfuse OTLP when configured.

Instrumentation never places prompts, completions, API keys or tool arguments in
span attributes. Full-payload capture is a separately encrypted ledger feature.
"""
from __future__ import annotations

import base64
import os
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

_PROVIDER = None


def setup_telemetry():
    global _PROVIDER
    host = os.getenv("DRAGONZPYDER_LANGFUSE_HOST", "").rstrip("/")
    public = os.getenv("DRAGONZPYDER_LANGFUSE_PUBLIC_KEY", "")
    secret = os.getenv("DRAGONZPYDER_LANGFUSE_SECRET_KEY", "")
    if not (host and public and secret):
        return False
    # Fail early instead of sending secret-bearing Basic Auth to plain HTTP.
    if not host.startswith("https://"):
        raise ValueError("Langfuse telemetry endpoint must use HTTPS")
    if _PROVIDER is not None:
        return True
    credentials = base64.b64encode(f"{public}:{secret}".encode()).decode()
    provider = TracerProvider(resource=Resource.create({
        "service.name": "dragonzpyder-inference",
        "deployment.environment.name": os.getenv("RAILWAY_ENVIRONMENT_NAME", "production"),
    }))
    provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint=host + "/api/public/otel/v1/traces",
            headers={"Authorization": "Basic " + credentials},
            timeout=8,
        ),
        max_queue_size=2048,
        max_export_batch_size=256,
    ))
    trace.set_tracer_provider(provider)
    _PROVIDER = provider
    return True


def shutdown_telemetry():
    global _PROVIDER
    if _PROVIDER is not None:
        _PROVIDER.shutdown()
        _PROVIDER = None


@contextmanager
def inference_span(request, app_id: str, model: str, request_id: str):
    tracer = trace.get_tracer("dragonzpyder.inference", "1.0.0")
    context = extract(dict(request.headers))
    with tracer.start_as_current_span("model.chat.completion", context=context) as span:
        span.set_attribute("gen_ai.system", "openrouter")
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("dragonzpyder.app_id", app_id)
        span.set_attribute("dragonzpyder.request_id", request_id)
        span.set_attribute("dragonzpyder.route", request.url.path)
        yield span


def span_trace_id(span) -> str:
    context = span.get_span_context()
    if context and context.is_valid:
        return f"{context.trace_id:032x}"
    return ""
