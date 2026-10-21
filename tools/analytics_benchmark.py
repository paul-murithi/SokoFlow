"""Real-provider benchmark for the integrated analytics conversation path.

Run this module with DATABASE_URL explicitly set to TEST_DB_URL and
BENCHMARK_ALLOW_LLM=1. It never sends a WhatsApp message.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import random
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.ai.contracts.llm import LLMResponse
from app.ai.executor import ToolExecutor
from app.ai.llm_client import LLMClient
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.redis import redis_client
from app.fsm.conversation_store import get_conversation_store
from app.fsm.models import InboundMessagePayload
from app.fsm.session_lua import register_session_update_script
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.sales import Sale
from app.models.shop import Shop
from app.workers import conversation_tasks

BENCHMARK_PHONE = "+254700000998"
BENCHMARK_SKU_PREFIX = "BENCH-"
DEFAULT_QUERIES = (
    ("sales_summary", "How much did I sell today?", "get_sales_summary"),
    ("stock_level", "Tell me the current inventory position for Sugar 1kg.", "get_stock_level"),
    ("top_products", "Rank products by sales performance this week.", "get_top_products"),
    ("low_stock", "Which items need replenishment?", "get_low_stock_items"),
    ("sales_trend", "Compare revenue this week with last week.", "get_sales_trend"),
    ("slow_moving", "Which products are not moving this month?", "get_slow_moving_items"),
    ("product_price", "What does Sugar 1kg cost?", "get_product_price"),
)


@dataclass
class Measurement:
    index: int
    case: str
    query: str
    expected_tool: str
    selected_tools: list[str]
    latency_ms: float
    outcome: str
    error_category: str | None
    error: str | None
    reply_ready: bool
    provider_request_attempted: bool = False
    provider_response_received: bool = False
    tool_execution_started: bool = False
    tool_execution_completed: bool = False
    formatted_reply_generated: bool = False
    failure_stage: str | None = None
    traceback: str | None = None
    provider_latency_ms: float | None = None
    tool_latency_ms: float | None = None


@dataclass
class RequestTrace:
    provider_request_attempted: bool = False
    provider_response_received: bool = False
    tool_execution_started: bool = False
    tool_execution_completed: bool = False
    formatted_reply_generated: bool = False
    provider_calls: int = 0
    tool_calls: int = 0
    provider_latency_ms: float | None = None
    tool_latency_ms: float | None = None


def _failure_stage(trace: RequestTrace) -> str:
    if not trace.provider_request_attempted:
        return "routing"
    if not trace.provider_response_received:
        return "provider"
    if not trace.tool_execution_started:
        return "provider_response"
    if not trace.tool_execution_completed:
        return "tool_execution"
    if not trace.formatted_reply_generated:
        return "formatting"
    return "validation"


def _sanitize_text(value: str) -> str:
    value = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)\S+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)\b(?:gsk_|sk-or-v1-)[A-Za-z0-9_-]+", "[REDACTED]", value)
    return value[:2000]


def percentile(values: list[float], percentage: float) -> float | None:
    """Return an interpolated percentile (linear rank, inclusive endpoints)."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentage / 100
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _require_safe_environment() -> None:
    if not settings.benchmark_allow_llm:
        raise RuntimeError(
            "Refusing to run: set BENCHMARK_ALLOW_LLM=1 to explicitly allow real provider calls."
        )
    if settings.app_env.lower() in {"production", "prod"}:
        raise RuntimeError("Refusing to run in a production application environment.")
    if not settings.test_db_url:
        raise RuntimeError("TEST_DB_URL is required for the benchmark.")
    if settings.database_url != settings.test_db_url:
        raise RuntimeError(
            "Refusing to run unless DATABASE_URL exactly equals TEST_DB_URL. "
            'Use: DATABASE_URL="$TEST_DB_URL".'
        )
    if settings.sender_backend.lower() == "whatsapp":
        raise RuntimeError("Refusing to run with the WhatsApp sender backend.")
    if not (settings.groq_api_key or settings.openrouter_api_key):
        raise RuntimeError("No LLM provider key configured (GROQ_API_KEY or OPENROUTER_API_KEY).")


async def _prepare_fixture() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        shop = (
            await session.execute(select(Shop).where(Shop.phone == BENCHMARK_PHONE))
        ).scalar_one_or_none()
        if shop is None:
            shop = Shop(phone=BENCHMARK_PHONE, name="SokoFlow Benchmark", locale="en")
            session.add(shop)
            await session.flush()
            products = [
                Product(
                    shop_id=shop.id,
                    name="Sugar 1kg",
                    price=Decimal("150.00"),
                    sku=f"{BENCHMARK_SKU_PREFIX}SUGAR",
                ),
                Product(
                    shop_id=shop.id,
                    name="Fresh Milk 500ml",
                    price=Decimal("60.00"),
                    sku=f"{BENCHMARK_SKU_PREFIX}MILK",
                ),
                Product(
                    shop_id=shop.id,
                    name="Iodized Salt 500g",
                    price=Decimal("35.00"),
                    sku=f"{BENCHMARK_SKU_PREFIX}SALT",
                ),
            ]
            session.add_all(products)
            await session.flush()
            session.add_all(
                [
                    Inventory(product_id=products[0].id, quantity=20, low_stock_threshold=5),
                    Inventory(product_id=products[1].id, quantity=2, low_stock_threshold=5),
                    Inventory(product_id=products[2].id, quantity=50, low_stock_threshold=5),
                    Sale(
                        shop_id=shop.id,
                        product_id=products[0].id,
                        quantity=10,
                        unit_price=Decimal("150.00"),
                        recorded_by="benchmark",
                    ),
                    Sale(
                        shop_id=shop.id,
                        product_id=products[0].id,
                        quantity=5,
                        unit_price=Decimal("150.00"),
                        recorded_by="benchmark",
                    ),
                ]
            )
            await session.commit()


class CaptureSender:
    def __init__(self) -> None:
        self.replies: list[str] = []

    def send_text(self, _recipient: str, message_text: str) -> None:
        self.replies.append(message_text)

    def send_document(
        self, _recipient: str, _document_bytes: bytes, _filename: str, _caption: str | None = None
    ) -> None:
        raise RuntimeError("The analytics benchmark must not deliver documents.")


def _payload(query: str, index: int) -> dict[str, object]:
    return InboundMessagePayload(
        sender=BENCHMARK_PHONE,
        message_text=query,
        message_id=f"benchmark-{uuid4()}-{index}",
        correlation_id=str(uuid4()),
    ).model_dump()


async def _run_request(
    item: tuple[str, str, str],
    index: int,
    sender: CaptureSender,
    trace: RequestTrace,
    selected_tools: list[str],
    timeout: float,
) -> Measurement:
    case, query, expected_tool = item
    selected_tools.clear()
    sender.replies.clear()
    trace.provider_request_attempted = False
    trace.provider_response_received = False
    trace.tool_execution_started = False
    trace.tool_execution_completed = False
    trace.formatted_reply_generated = False
    trace.provider_calls = 0
    trace.tool_calls = 0
    trace.provider_latency_ms = None
    trace.tool_latency_ms = None
    started = time.perf_counter()
    error_category: str | None = None
    error_message: str | None = None
    error_traceback: str | None = None
    failure_stage: str | None = None
    outcome = "success"
    try:
        await asyncio.wait_for(conversation_tasks.conversation(_payload(query, index)), timeout)
        reply_ready = bool(sender.replies and sender.replies[-1].strip())
        trace.formatted_reply_generated = reply_ready
        if not trace.provider_request_attempted:
            outcome = "failed"
            failure_stage = "routing"
            error_category = "not_entered_analytics"
            error_message = "Request did not enter the analytics LLM boundary."
        elif not trace.provider_response_received:
            outcome = "failed"
            failure_stage = "provider"
            error_category = "no_provider_response"
            error_message = "Provider request did not produce a response."
        elif not selected_tools:
            outcome = "invalid_response"
            failure_stage = "provider_response"
            error_category = "no_tool_selected"
            error_message = "Provider response contained no analytics tool call."
        elif not trace.tool_execution_started:
            outcome = "failed"
            failure_stage = "tool_execution"
            error_category = "tool_execution"
            error_message = "No tool execution began after provider tool selection."
        elif not trace.tool_execution_completed:
            outcome = "failed"
            failure_stage = "tool_execution"
            error_category = "tool_execution"
            error_message = "Tool execution did not complete successfully."
        elif not reply_ready:
            outcome = "invalid_response"
            failure_stage = "formatting"
            error_category = "empty_reply"
            error_message = "Analytics execution completed without a formatted reply."
        elif selected_tools[-1] != expected_tool:
            outcome = "wrong_tool"
            failure_stage = "validation"
            error_category = "unexpected_tool"
    except TimeoutError as exc:
        outcome = "timeout"
        failure_stage = _failure_stage(trace)
        error_category = "timeout"
        error_message = _sanitize_text(str(exc) or f"request exceeded {timeout:.1f}s")
        reply_ready = False
    except Exception as exc:
        outcome = "failed"
        failure_stage = _failure_stage(trace)
        error_category = type(exc).__name__
        error_message = _sanitize_text(str(exc))
        if settings.debug:
            import traceback

            error_traceback = _sanitize_text(traceback.format_exc())
        reply_ready = False
    return Measurement(
        index=index,
        case=case,
        query=query,
        expected_tool=expected_tool,
        selected_tools=list(selected_tools),
        latency_ms=(time.perf_counter() - started) * 1000,
        outcome=outcome,
        error_category=error_category,
        error=error_message,
        reply_ready=reply_ready,
        provider_request_attempted=trace.provider_request_attempted,
        provider_response_received=trace.provider_response_received,
        tool_execution_started=trace.tool_execution_started,
        tool_execution_completed=trace.tool_execution_completed,
        formatted_reply_generated=trace.formatted_reply_generated,
        failure_stage=failure_stage,
        traceback=error_traceback,
        provider_latency_ms=trace.provider_latency_ms,
        tool_latency_ms=trace.tool_latency_ms,
    )


def _aggregate(measurements: list[Measurement], args: argparse.Namespace) -> dict[str, Any]:
    successful = [m for m in measurements if m.outcome == "success"]
    failed = [m for m in measurements if m.outcome != "success"]
    successful_latencies = [m.latency_ms for m in successful]
    failed_latencies = [m.latency_ms for m in failed]
    per_tool: dict[str, dict[str, Any]] = {}
    for tool in sorted({m.expected_tool for m in measurements}):
        group = [m for m in measurements if m.expected_tool == tool]
        good = [m for m in group if m.outcome == "success"]
        per_tool[tool] = {
            "requests": len(group),
            "successful": len(good),
            "p50_ms": percentile([m.latency_ms for m in good], 50),
            "p95_ms": percentile([m.latency_ms for m in good], 95),
            "valid_samples": len(good),
        }
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "provider_endpoint": settings.llm_provider_endpoint,
        "model": settings.llm_model,
        "real_dependencies": True,
        "stubs_used": False,
        "warmup_requests": args.warmup,
        "total_attempted_requests": len(measurements),
        "measured_requests": len(measurements),
        "successful_requests": len(successful),
        "success_rate": len(successful) / len(measurements) if measurements else 0.0,
        "failed_requests": len(measurements) - len(successful),
        "wrong_tool_selections": sum(m.outcome == "wrong_tool" for m in measurements),
        "timeouts": sum(m.outcome == "timeout" for m in measurements),
        "failure_stages": _counts_by(
            [measurement for measurement in measurements if measurement.outcome != "success"],
            "failure_stage",
        ),
        "successful_response_p50_ms": percentile(successful_latencies, 50),
        "successful_response_p95_ms": percentile(successful_latencies, 95),
        "successful_response_max_ms": max(successful_latencies, default=None),
        "successful_response_valid_samples": len(successful_latencies),
        "failed_request_p50_ms": percentile(failed_latencies, 50),
        "failed_request_p95_ms": percentile(failed_latencies, 95),
        "failed_request_max_ms": max(failed_latencies, default=None),
        "failed_request_samples": len(failed_latencies),
        "percentile_method": (
            "linear interpolation over sorted measured latencies (inclusive endpoints)"
        ),
        "measurement_boundary": (
            "conversation() entry through formatted reply handed to captured send_text; "
            "excludes webhook HTTP parsing, Celery queue wait, and WhatsApp network delivery"
        ),
        "per_tool": per_tool,
        "limitations": (
            "Small samples are diagnostic and are not statistically reliable "
            "production p95 estimates."
        ),
        "valid_latency_result": bool(successful_latencies),
        "successful_percentiles_note": (
            "No valid successful analytics responses were recorded."
            if not successful_latencies
            else "Computed only from successful, validated analytics responses."
        ),
    }


def _counts_by(measurements: list[Measurement], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for measurement in measurements:
        value = getattr(measurement, field) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return counts


def _write_outputs(
    output_dir: Path, report: dict[str, Any], measurements: list[Measurement]
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analytics-benchmark-report.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
    )
    with (output_dir / "analytics-benchmark-measurements.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(measurements[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(measurement) for measurement in measurements)


async def _cleanup_resources() -> None:
    """Close benchmark-owned application resources before asyncio.run exits."""
    try:
        await engine.dispose()
    finally:
        await redis_client.aclose()


async def _reset_benchmark_session() -> None:
    """Remove only the dedicated benchmark conversation state before a run."""
    await get_conversation_store().delete_session(BENCHMARK_PHONE)


async def _benchmark(args: argparse.Namespace) -> int:
    _require_safe_environment()
    try:
        await _prepare_fixture()
        register_session_update_script(get_conversation_store().redis)
        await _reset_benchmark_session()
        sender = CaptureSender()
        original_sender = conversation_tasks.MESSAGE_SENDER
        original_generate = LLMClient.generate
        original_execute = ToolExecutor.execute
        selected_tools: list[str] = []
        trace = RequestTrace()

        async def observe_generate(
            self: LLMClient, *call_args: Any, **call_kwargs: Any
        ) -> LLMResponse:
            trace.provider_request_attempted = True
            trace.provider_calls += 1
            started = time.perf_counter()
            try:
                response = await original_generate(self, *call_args, **call_kwargs)
            finally:
                trace.provider_latency_ms = (time.perf_counter() - started) * 1000
            trace.provider_response_received = True
            selected_tools.extend(call.name for call in response.tool_calls)
            return response

        async def observe_execute(self: ToolExecutor, *call_args: Any, **call_kwargs: Any) -> Any:
            trace.tool_execution_started = True
            trace.tool_calls += 1
            started = time.perf_counter()
            try:
                result = await original_execute(self, *call_args, **call_kwargs)
            finally:
                trace.tool_latency_ms = (time.perf_counter() - started) * 1000
            trace.tool_execution_completed = result.is_success
            return result

        setattr(conversation_tasks, "MESSAGE_SENDER", sender)
        setattr(LLMClient, "generate", observe_generate)
        setattr(ToolExecutor, "execute", observe_execute)
        try:
            for index in range(args.warmup):
                await _run_request(
                    DEFAULT_QUERIES[index % len(DEFAULT_QUERIES)],
                    index,
                    sender,
                    trace,
                    selected_tools,
                    args.timeout,
                )
            queries = list(DEFAULT_QUERIES)
            random.Random(args.seed).shuffle(queries)
            measurements = [
                await _run_request(
                    queries[index % len(queries)],
                    index,
                    sender,
                    trace,
                    selected_tools,
                    args.timeout,
                )
                for index in range(args.requests)
            ]
        finally:
            setattr(conversation_tasks, "MESSAGE_SENDER", original_sender)
            setattr(LLMClient, "generate", original_generate)
            setattr(ToolExecutor, "execute", original_execute)
    finally:
        await _cleanup_resources()

    report = _aggregate(measurements, args)
    _write_outputs(Path(args.output_dir), report, measurements)
    print(json.dumps(report, indent=2, default=str))
    return 0 if all(m.outcome == "success" for m in measurements) else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--requests", type=int, default=7)
    parser.add_argument("--seed", type=int, default=3)
    parser.add_argument(
        "--timeout", type=float, default=max(60.0, settings.llm_timeout_seconds * 3)
    )
    parser.add_argument("--output-dir", default="benchmark-results")
    args = parser.parse_args()
    if args.warmup < 0 or args.requests < 1 or args.timeout <= 0:
        parser.error("warmup must be >= 0, requests and timeout must be positive")

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        return asyncio.run(_benchmark(args))
    except (RuntimeError, OSError) as exc:
        print(f"benchmark configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
