"""Unit tests for LLMClient provider boundary."""

import httpx
import pytest

from app.ai.contracts.llm import LLMMessage, LLMResponse, NormalizedToolCall
from app.ai.errors import (
    LLMProviderAPIError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
    LLMResponseFormatError,
)
from app.ai.llm_client import LLMClient


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
