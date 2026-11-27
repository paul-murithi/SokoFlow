"""LLMClient Component — SokoFlow Provider Boundary and Gateway.

Isolates external LLM provider communication (Groq/OpenAI-compatible APIs) behind
a SokoFlow-owned input/output contract interface.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.ai.contracts.llm import LLMMessage, LLMResponse, NormalizedToolCall
from app.ai.errors import (
    LLMProviderAPIError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
    LLMResponseFormatError,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """You select exactly one SokoFlow analytics function for each
merchant question.
Use only the supplied tools. Never provide shop_id; shop scope is controlled by the
application.
For a clear analytics request, always return the matching function call. If intent or a
required detail is genuinely unclear, ask a brief clarification instead of guessing.

CRITICAL PARAMETER RULES:
1. For tools requiring a 'period' parameter (get_sales_summary, get_top_products,
   get_sales_trend, get_slow_moving_items):
   'period' MUST be a JSON object. For relative periods, use 'period_type': 'relative',
   'relative_period' ('day', 'week', 'month', 'year'), and optional 'period_offset'
   (0 for the current period, -1 for the immediately previous period). For explicit dates,
   use 'period_type': 'date_range', 'date_range' with ISO 'start_date' and 'end_date', and
   omit 'relative_period'.
   Examples:
   - 'today': {"period_type": "relative", "relative_period": "day"}
   - 'this week': {"period_type": "relative", "relative_period": "week"}
   - 'last week': {"period_type": "relative", "relative_period": "week", "period_offset": -1}
   - 'this month': {"period_type": "relative", "relative_period": "month"}
   - 'last year': {"period_type": "relative", "relative_period": "year", "period_offset": -1}
   - 'between 2026-11-01 and 2026-11-03': {"period_type": "date_range", "date_range":
     {"start_date": "2026-11-01", "end_date": "2026-11-03"}}

2. Select get_sales_trend for requests to compare sales periods or assess whether sales are
   rising or falling. Its 'period' is the primary/current period; the tool compares it with
   the immediately previous period unless a distinct comparison_period is requested.

3. For get_top_products, map 'most units' or 'units sold' to ranking_dimension 'units',
   and 'highest revenue' or 'sales value' to 'revenue'. Omit ranking_dimension if both
   rankings are requested. For a clear 'top items' request with no period stated, use day.

4. For get_stock_level, provide product_name when the user gives a product name and no UUID.
   Never invent or use a placeholder product_id. The application resolves product names.
"""

MAX_RETRY_AFTER_SECONDS = 60.0


class LLMClient:
    """Gateway and translator for SokoFlow external LLM provider communication."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key or settings.groq_api_key or settings.openrouter_api_key or ""
        self.endpoint = endpoint or settings.llm_provider_endpoint
        self.model = model or settings.llm_model
        self.timeout = timeout if timeout is not None else settings.llm_timeout_seconds
        self._http_client = http_client

    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Sends messages and tools to the provider and returns a normalized LLMResponse.

        Translates provider response structures into LLMResponse and provider errors into
        SokoFlow application-level exceptions.
        """
        payload_messages: list[dict[str, Any]] = []

        # Injects standard system prompt if provided or default
        effective_system_prompt = (
            system_prompt if system_prompt is not None else DEFAULT_SYSTEM_PROMPT
        )
        if effective_system_prompt:
            payload_messages.append({"role": "system", "content": effective_system_prompt})

        for msg in messages:
            payload_messages.append({"role": msg.role, "content": msg.content or ""})

        input_chars = sum(len(message["content"]) for message in payload_messages)
        if tools:
            input_chars += len(json.dumps(tools, default=str))
        if input_chars > settings.analytics_max_input_chars:
            raise LLMResponseFormatError(
                "Analytics provider input exceeds the configured size limit."
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or settings.analytics_max_output_tokens,
            "stream": False,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        started_at = time.perf_counter()
        raw_payload = await self._post_payload(payload, headers)
        latency_ms = (time.perf_counter() - started_at) * 1000.0

        logger.debug(
            "LLM provider call to %s completed in %.2f ms",
            self.model,
            latency_ms,
        )

        return self._normalize_response(raw_payload)

    async def _post_payload(
        self, payload: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        """Executes HTTP request to provider with retry handling.

        Retries HTTP 429 responses using a bounded Retry-After or exponential backoff.
        Other HTTP and transport failures are translated without retrying.
        """
        client_created = False
        client = self._http_client
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout)
            client_created = True

        try:
            return await asyncio.wait_for(
                self._post_payload_with_retries(client, payload, headers),
                timeout=settings.llm_request_deadline_seconds,
            )
        except TimeoutError as exc:
            logger.warning(
                "LLM provider request exceeded its %.1fs overall deadline",
                settings.llm_request_deadline_seconds,
            )
            raise LLMProviderTimeoutError(
                "LLM provider request exceeded its overall deadline.",
                original_exception=exc,
            ) from exc
        finally:
            if client_created:
                await client.aclose()

    async def _post_payload_with_retries(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Posts and handles retries within the caller's overall request deadline."""
        max_retries = settings.llm_max_retries
        attempt = 0
        while True:
            try:
                response = await client.post(self.endpoint, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                logger.warning("LLM provider request timed out after %.1fs", self.timeout)
                raise LLMProviderTimeoutError(
                    f"LLM provider request timed out after {self.timeout}s.",
                    original_exception=exc,
                ) from exc
            except httpx.RequestError as exc:
                logger.warning("LLM provider transport error: %s", exc)
                raise LLMProviderUnavailableError(
                    f"LLM provider is unreachable: {exc}", original_exception=exc
                ) from exc

            if response.status_code != 429:
                break
            if attempt >= max_retries:
                raise LLMProviderAPIError(
                    f"Exceeded max retries ({max_retries}) after rate-limit responses.",
                    status_code=429,
                )

            wait_seconds = self._retry_after_seconds(response.headers.get("Retry-After"))
            if wait_seconds is None:
                backoff = settings.llm_initial_backoff * (2**attempt)
                wait_seconds = backoff + backoff * 0.1 * random.random()
            wait_seconds = min(max(wait_seconds, 0.0), MAX_RETRY_AFTER_SECONDS)
            logger.warning(
                "Rate limit hit (HTTP 429). Waiting %.2f seconds before retry #%d",
                wait_seconds,
                attempt + 1,
            )
            await asyncio.sleep(wait_seconds)
            attempt += 1

        if response.status_code >= 500:
            logger.error("LLM provider 5xx response: HTTP %d", response.status_code)
            raise LLMProviderUnavailableError(
                f"LLM provider service error: HTTP {response.status_code}"
            )
        if response.status_code >= 400:
            logger.error("LLM provider 4xx response: HTTP %d", response.status_code)
            raise LLMProviderAPIError(
                f"LLM provider API error: HTTP {response.status_code}",
                status_code=response.status_code,
            )

        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Response body is not a JSON object")
            return data
        except Exception as exc:
            logger.error("LLM provider output parse error: %s", exc)
            raise LLMResponseFormatError(
                f"Failed to parse LLM provider JSON response: {exc}", original_exception=exc
            ) from exc

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float | None:
        """Parse Retry-After delta-seconds or HTTP-date, rejecting invalid values."""
        if value is None:
            return None
        try:
            seconds = float(value)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                return None
        if not math.isfinite(seconds) or seconds < 0:
            return None
        return seconds

    def _normalize_response(self, raw_payload: dict[str, Any]) -> LLMResponse:
        """Translates raw OpenAI-compatible response dict into normalized LLMResponse."""
        choices = raw_payload.get("choices")
        text_content: str | None = None
        normalized_tool_calls: list[NormalizedToolCall] = []

        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message")
                if isinstance(message, dict):
                    text_content = message.get("content")

                    raw_tool_calls = message.get("tool_calls")
                    if isinstance(raw_tool_calls, list):
                        for tc in raw_tool_calls:
                            if not isinstance(tc, dict):
                                continue
                            func = tc.get("function")
                            if not isinstance(func, dict):
                                continue

                            tool_name = func.get("name")
                            if not isinstance(tool_name, str) or not tool_name:
                                continue

                            raw_args = func.get("arguments", {})
                            parsed_args: dict[str, Any] = {}
                            if isinstance(raw_args, str):
                                try:
                                    parsed_args = json.loads(raw_args) if raw_args.strip() else {}
                                except json.JSONDecodeError as exc:
                                    raise LLMResponseFormatError(
                                        f"Malformed tool call arguments JSON for "
                                        f"'{tool_name}': {exc.msg}",
                                        original_exception=exc,
                                    ) from exc
                            elif isinstance(raw_args, dict):
                                parsed_args = raw_args

                            if not isinstance(parsed_args, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
                                raise LLMResponseFormatError(
                                    f"Tool call arguments for '{tool_name}' must be a JSON object."
                                )

                            tc_id = tc.get("id")
                            normalized_tool_calls.append(
                                NormalizedToolCall(
                                    id=str(tc_id) if tc_id else None,
                                    name=tool_name,
                                    arguments=parsed_args,
                                )
                            )

        # Fallback check for rejected generation payloads (e.g. Groq failed_generation)
        if not normalized_tool_calls:
            error_obj = raw_payload.get("error")
            if isinstance(error_obj, dict):
                failed_gen = error_obj.get("failed_generation")
                if failed_gen:
                    func_obj = None
                    if isinstance(failed_gen, str):
                        try:
                            func_obj = json.loads(failed_gen)
                        except json.JSONDecodeError:
                            pass
                    elif isinstance(failed_gen, dict):
                        func_obj = failed_gen

                    if isinstance(func_obj, dict):
                        t_name = func_obj.get("name")
                        r_args = func_obj.get("arguments", {})
                        if isinstance(t_name, str) and t_name:
                            p_args = {}
                            if isinstance(r_args, str):
                                try:
                                    p_args = json.loads(r_args)
                                except json.JSONDecodeError:
                                    pass
                            elif isinstance(r_args, dict):
                                p_args = r_args

                            if isinstance(p_args, dict):
                                normalized_tool_calls.append(
                                    NormalizedToolCall(
                                        id=None,
                                        name=t_name,
                                        arguments=p_args,
                                    )
                                )

        # Usage and cost accounting
        usage = raw_payload.get("usage", {}) if isinstance(raw_payload, dict) else {}  # pyright: ignore[reportUnnecessaryIsInstance]
        prompt_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
        completion_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None

        cost_usd: float | None = None
        if isinstance(usage, dict) and "cost" in usage and usage["cost"] is not None:
            try:
                cost_usd = float(usage["cost"])
            except (ValueError, TypeError):
                cost_usd = None

        return LLMResponse(
            text=text_content,
            tool_calls=normalized_tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            raw_response=raw_payload,
        )
