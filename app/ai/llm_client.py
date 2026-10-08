"""LLMClient Component — SokoFlow Provider Boundary and Gateway.

Isolates external LLM provider communication (Groq/OpenAI-compatible APIs) behind
a SokoFlow-owned input/output contract interface.
"""

from __future__ import annotations

import json
import logging
import time
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
Return a function call when the request can be represented by a tool; otherwise reply briefly
that clarification is needed.

CRITICAL PARAMETER RULES:
1. For tools requiring a 'period' parameter (get_sales_summary, get_top_products,
   get_sales_trend, get_slow_moving_items):
   'period' MUST be a JSON object with 'period_type' ('relative' or 'date_range') and
   'relative_period' ('day', 'week', 'month', 'year').
   Examples:
   - 'today': {"period_type": "relative", "relative_period": "day"}
   - 'this week': {"period_type": "relative", "relative_period": "week"}
   - 'this month': {"period_type": "relative", "relative_period": "month"}
   - 'last year' / 'this year': {"period_type": "relative", "relative_period": "year"}

2. For get_stock_level (used for stock level or product price queries for a specific
   product):
   If a product UUID is not explicitly provided in user text, pass placeholder UUID
   '00000000-0000-0000-0000-000000000000' for product_id.
"""


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
        max_tokens: int = 256,
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

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
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
        """Executes HTTP request to provider and handles low-level transport errors."""
        client_created = False
        client = self._http_client
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout)
            client_created = True

        try:
            response = await client.post(
                self.endpoint,
                headers=headers,
                json=payload,
            )
        except httpx.TimeoutException as exc:
            logger.warning("LLM provider request timed out after %.1fs", self.timeout)
            raise LLMProviderTimeoutError(
                f"LLM provider request timed out after {self.timeout}s.", original_exception=exc
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("LLM provider transport error: %s", exc)
            raise LLMProviderUnavailableError(
                f"LLM provider is unreachable: {exc}", original_exception=exc
            ) from exc
        finally:
            if client_created:
                await client.aclose()

        if response.status_code >= 500:
            logger.error("LLM provider 5xx response: HTTP %d", response.status_code)
            raise LLMProviderUnavailableError(
                f"LLM provider service error: HTTP {response.status_code}"
            )

        if response.status_code >= 400:
            logger.error(
                "LLM provider 4xx response: HTTP %d - %s", response.status_code, response.text
            )
            raise LLMProviderAPIError(
                f"LLM provider API error: HTTP {response.status_code} - {response.text[:200]}",
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
        prompt_tokens = usage.get("prompt_tokens", 0) if isinstance(usage, dict) else 0
        completion_tokens = usage.get("completion_tokens", 0) if isinstance(usage, dict) else 0

        cost_usd = 0.0
        if isinstance(usage, dict) and "cost" in usage and usage["cost"] is not None:
            try:
                cost_usd = float(usage["cost"])
            except (ValueError, TypeError):
                cost_usd = 0.0

        return LLMResponse(
            text=text_content,
            tool_calls=normalized_tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            raw_response=raw_payload,
        )
