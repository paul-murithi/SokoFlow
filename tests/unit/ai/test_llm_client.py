"""Unit tests for LLMClient provider boundary."""

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from app.ai.contracts.llm import LLMMessage, LLMResponse, NormalizedToolCall
from app.ai.errors import (
    LLMProviderAPIError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
    LLMResponseFormatError,
)
from app.ai.llm_client import DEFAULT_SYSTEM_PROMPT, LLMClient


def test_default_prompt_uses_supported_tool_contracts():
    assert "Never invent or use a placeholder product_id" in DEFAULT_SYSTEM_PROMPT
    assert '"period_offset": -1' in DEFAULT_SYSTEM_PROMPT
    assert '"period_type": "date_range"' in DEFAULT_SYSTEM_PROMPT
    assert "ranking_dimension 'units'" in DEFAULT_SYSTEM_PROMPT
    assert "no period stated, use day" in DEFAULT_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_llm_client_successful_tool_call():
    provider_payload = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-001",
                            "type": "function",
                            "function": {
                                "name": "get_sales_summary",
                                "arguments": (
                                    '{"period": {"period_type": "relative", '
                                    '"relative_period": "day"}}'
                                ),
                            },
                        }
                    ],
                }
            }
        ],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 45,
        },
    }

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=provider_payload)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient(api_key="test-key", http_client=http_client)
        response = await client.generate(
            messages=[LLMMessage(role="user", content="How much did I sell today?")]
        )

        assert isinstance(response, LLMResponse)
        assert response.text is None
        assert response.has_tool_calls is True
        assert len(response.tool_calls) == 1

        tool_call = response.primary_tool_call
        assert isinstance(tool_call, NormalizedToolCall)
        assert tool_call.name == "get_sales_summary"
        assert tool_call.arguments == {
            "period": {"period_type": "relative", "relative_period": "day"}
        }
        assert response.prompt_tokens == 120
        assert response.completion_tokens == 45


@pytest.mark.asyncio
async def test_llm_client_successful_text_response():
    provider_payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Please clarify which product you mean.",
                }
            }
        ],
        "usage": {"prompt_tokens": 80, "completion_tokens": 15},
    }

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=provider_payload)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient(api_key="test-key", http_client=http_client)
        response = await client.generate(
            messages=[LLMMessage(role="user", content="What is the price?")]
        )

        assert response.text == "Please clarify which product you mean."
        assert response.has_tool_calls is False
        assert response.primary_tool_call is None


@pytest.mark.asyncio
async def test_llm_client_retries_rate_limited_request(monkeypatch):
    calls = 0

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}], "usage": {}},
        )

    monkeypatch.setattr("app.core.config.settings.llm_max_retries", 1)
    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient(api_key="test-key", http_client=http_client)
        response = await client.generate(
            messages=[LLMMessage(role="user", content="How much did I sell today?")]
        )

    assert response.text == "ok"
    assert calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "post_error",
    [
        httpx.TimeoutException("timed out"),
        httpx.ConnectError("connection failed"),
        asyncio.CancelledError(),
    ],
)
async def test_locally_created_http_client_is_closed_on_exceptions(monkeypatch, post_error):
    local_client = AsyncMock()
    local_client.post.side_effect = post_error
    monkeypatch.setattr("app.ai.llm_client.httpx.AsyncClient", lambda **_: local_client)
    client = LLMClient(api_key="test-key")

    with pytest.raises(
        (LLMProviderTimeoutError, LLMProviderUnavailableError, asyncio.CancelledError)
    ):
        await client.generate(messages=[LLMMessage(role="user", content="Test")])

    local_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_locally_created_http_client_is_closed_after_retry_exhaustion(monkeypatch):
    local_client = AsyncMock()
    local_client.post.return_value = httpx.Response(429, request=httpx.Request("POST", "https://x"))
    monkeypatch.setattr("app.ai.llm_client.httpx.AsyncClient", lambda **_: local_client)
    monkeypatch.setattr("app.core.config.settings.llm_max_retries", 0)
    client = LLMClient(api_key="test-key")

    with pytest.raises(LLMProviderAPIError):
        await client.generate(messages=[LLMMessage(role="user", content="Test")])

    local_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_overall_deadline_interrupts_retry_wait_and_closes_client(monkeypatch):
    local_client = AsyncMock()
    local_client.post.return_value = httpx.Response(
        429,
        headers={"Retry-After": "60"},
        request=httpx.Request("POST", "https://x"),
    )
    monkeypatch.setattr("app.ai.llm_client.httpx.AsyncClient", lambda **_: local_client)
    monkeypatch.setattr("app.core.config.settings.llm_request_deadline_seconds", 0.01)
    client = LLMClient(api_key="test-key")

    with pytest.raises(LLMProviderTimeoutError, match="overall deadline"):
        await client.generate(messages=[LLMMessage(role="user", content="Test")])

    local_client.post.assert_awaited_once()
    local_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_retry_after_is_capped_and_provider_error_body_is_not_exposed(monkeypatch, caplog):
    local_client = AsyncMock()
    local_client.post.side_effect = [
        httpx.Response(
            429,
            headers={"Retry-After": "3600"},
            request=httpx.Request("POST", "https://x"),
        ),
        httpx.Response(
            400,
            text="sensitive echoed request",
            request=httpx.Request("POST", "https://x"),
        ),
    ]
    monkeypatch.setattr("app.ai.llm_client.httpx.AsyncClient", lambda **_: local_client)
    monkeypatch.setattr("app.core.config.settings.llm_max_retries", 1)
    sleep = AsyncMock()
    monkeypatch.setattr("app.ai.llm_client.asyncio.sleep", sleep)
    client = LLMClient(api_key="test-key")

    with pytest.raises(LLMProviderAPIError) as exc_info:
        await client.generate(messages=[LLMMessage(role="user", content="Test")])

    sleep.assert_awaited_once_with(60.0)
    assert "sensitive echoed request" not in str(exc_info.value)
    assert "sensitive echoed request" not in caplog.text
    local_client.aclose.assert_awaited_once()


@pytest.mark.parametrize(
    "value",
    ["0", "-5", "3600", "inf", "nan", "not-a-number"],
)
def test_retry_after_parser_accepts_only_finite_nonnegative_values(value):
    parsed = LLMClient._retry_after_seconds(value)
    if value == "0" or value == "3600":
        assert parsed == float(value)
    else:
        assert parsed is None


def test_retry_after_parser_accepts_http_date():
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime

    retry_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    parsed = LLMClient._retry_after_seconds(format_datetime(retry_at, usegmt=True))

    assert parsed is not None
    assert 0 < parsed <= 30


@pytest.mark.asyncio
async def test_llm_client_response_no_text_no_tools():
    provider_payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                }
            }
        ]
    }

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=provider_payload)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient(api_key="test-key", http_client=http_client)
        response = await client.generate(messages=[LLMMessage(role="user", content="Hello")])

        assert response.text is None
        assert response.has_tool_calls is False
        assert response.primary_tool_call is None


@pytest.mark.asyncio
async def test_llm_client_timeout_translation():
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out", request=request)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient(api_key="test-key", http_client=http_client)
        with pytest.raises(LLMProviderTimeoutError) as exc_info:
            await client.generate(messages=[LLMMessage(role="user", content="Test")])
        assert "timed out" in str(exc_info.value)


@pytest.mark.asyncio
async def test_llm_client_5xx_unavailable_translation():
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient(api_key="test-key", http_client=http_client)
        with pytest.raises(LLMProviderUnavailableError) as exc_info:
            await client.generate(messages=[LLMMessage(role="user", content="Test")])
        assert "503" in str(exc_info.value)


@pytest.mark.asyncio
async def test_llm_client_4xx_api_error_translation():
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Bad Request: invalid model")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient(api_key="test-key", http_client=http_client)
        with pytest.raises(LLMProviderAPIError) as exc_info:
            await client.generate(messages=[LLMMessage(role="user", content="Test")])
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_llm_client_malformed_arguments_json():
    provider_payload = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "call-002",
                            "function": {
                                "name": "get_sales_summary",
                                "arguments": '{"period": invalid json syntax}',
                            },
                        }
                    ]
                }
            }
        ]
    }

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=provider_payload)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient(api_key="test-key", http_client=http_client)
        with pytest.raises(LLMResponseFormatError) as exc_info:
            await client.generate(messages=[LLMMessage(role="user", content="Test")])
        assert "Malformed tool call arguments" in str(exc_info.value)


@pytest.mark.asyncio
async def test_llm_client_failed_generation_fallback():
    provider_payload = {
        "choices": [],
        "error": {
            "message": "Tool call validation failed",
            "failed_generation": (
                '{"name": "get_sales_summary", "arguments": {"period": '
                '{"period_type": "relative", "relative_period": "day"}}}'
            ),
        },
    }

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=provider_payload)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient(api_key="test-key", http_client=http_client)
        response = await client.generate(messages=[LLMMessage(role="user", content="Test")])

        assert response.has_tool_calls is True
        assert response.primary_tool_call.name == "get_sales_summary"


@pytest.mark.asyncio
async def test_llm_client_network_error_translation():
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Failed to connect to host", request=request)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient(api_key="test-key", http_client=http_client)
        with pytest.raises(LLMProviderUnavailableError) as exc_info:
            await client.generate(messages=[LLMMessage(role="user", content="Test")])
        assert "unreachable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_llm_client_non_dict_arguments_error():
    provider_payload = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "call-003",
                            "function": {
                                "name": "get_sales_summary",
                                "arguments": '"just a string"',
                            },
                        }
                    ]
                }
            }
        ]
    }

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=provider_payload)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LLMClient(api_key="test-key", http_client=http_client)
        with pytest.raises(LLMResponseFormatError) as exc_info:
            await client.generate(messages=[LLMMessage(role="user", content="Test")])
        assert "must be a JSON object" in str(exc_info.value)
