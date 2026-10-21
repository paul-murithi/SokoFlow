from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from tools.analytics_benchmark import Measurement, _aggregate, percentile


def test_percentile_interpolates_and_handles_small_samples():
    assert percentile([], 95) is None
    assert percentile([7], 50) == 7
    assert percentile([10, 20, 30, 40], 50) == 25
    assert percentile([10, 20, 30, 40], 95) == 38.5


def test_aggregate_reports_failures_and_success_metrics():
    measurements = [
        Measurement(0, "a", "q", "tool_a", ["tool_a"], 10, "success", None, None, True),
        Measurement(
            index=1,
            case="b",
            query="q",
            expected_tool="tool_b",
            selected_tools=["tool_a"],
            latency_ms=30,
            outcome="wrong_tool",
            error_category="unexpected_tool",
            error=None,
            reply_ready=True,
            failure_stage="validation",
        ),
        Measurement(
            index=2,
            case="c",
            query="q",
            expected_tool="tool_a",
            selected_tools=[],
            latency_ms=20,
            outcome="timeout",
            error_category="timeout",
            error="late",
            reply_ready=False,
            failure_stage="provider",
        ),
    ]
    report = _aggregate(measurements, Namespace(warmup=1))
    assert report["measured_requests"] == 3
    assert report["successful_requests"] == 1
    assert report["wrong_tool_selections"] == 1
    assert report["timeouts"] == 1
    assert report["successful_response_p50_ms"] == 10
    assert report["successful_response_p95_ms"] == 10
    assert report["failure_stages"] == {"validation": 1, "provider": 1}
    assert report["per_tool"]["tool_a"]["successful"] == 1


def test_zero_success_reports_null_successful_percentiles():
    measurements = [
        Measurement(
            index=0,
            case="a",
            query="q",
            expected_tool="tool_a",
            selected_tools=[],
            latency_ms=10,
            outcome="failed",
            error_category="routing",
            error="not routed",
            reply_ready=True,
            formatted_reply_generated=True,
            failure_stage="routing",
        )
    ]
    report = _aggregate(measurements, Namespace(warmup=0))
    assert report["successful_requests"] == 0
    assert report["successful_response_p50_ms"] is None
    assert report["successful_response_p95_ms"] is None
    assert report["failed_request_p50_ms"] == 10
    assert report["valid_latency_result"] is False


@pytest.mark.asyncio
async def test_provider_exception_is_recorded_at_provider_stage(monkeypatch):
    from tools import analytics_benchmark as benchmark

    async def fail(_payload):
        trace.provider_request_attempted = True
        raise RuntimeError("provider timed out")

    monkeypatch.setattr(benchmark.conversation_tasks, "conversation", fail)
    trace = benchmark.RequestTrace()
    measurement = await benchmark._run_request(
        benchmark.DEFAULT_QUERIES[0],
        0,
        benchmark.CaptureSender(),
        trace,
        [],
        1,
    )
    assert measurement.outcome == "failed"
    assert measurement.failure_stage == "provider"
    assert measurement.error_category == "RuntimeError"
    assert measurement.error == "provider timed out"


@pytest.mark.asyncio
async def test_cleanup_closes_resources_while_loop_is_running(monkeypatch):
    from tools import analytics_benchmark as benchmark

    engine_dispose = AsyncMock()
    redis_close = AsyncMock()
    monkeypatch.setattr(benchmark, "engine", SimpleNamespace(dispose=engine_dispose))
    monkeypatch.setattr(benchmark, "redis_client", SimpleNamespace(aclose=redis_close))

    await benchmark._cleanup_resources()

    engine_dispose.assert_awaited_once()
    redis_close.assert_awaited_once()


def test_safety_gate_requires_explicit_test_database_and_opt_in(monkeypatch):
    monkeypatch.delenv("BENCHMARK_ALLOW_LLM", raising=False)
    monkeypatch.setattr(settings, "benchmark_allow_llm", False)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "test_db_url", "postgresql+asyncpg://localhost/test")
    monkeypatch.setattr(settings, "database_url", "postgresql+asyncpg://localhost/production")

    from tools.analytics_benchmark import _require_safe_environment

    with pytest.raises(RuntimeError, match="BENCHMARK_ALLOW_LLM"):
        _require_safe_environment()
